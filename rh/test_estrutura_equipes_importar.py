import io
import json

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from organization.models import AlocacaoPosto, GrupoEquipe, Setor, SetorEquipe
from rh.models import Colaborador
from rh.services.estrutura_import import PlanilhaInvalida, ler_planilha


def xlsx_bytes(linhas):
    wb = Workbook()
    ws = wb.active
    for linha in linhas:
        ws.append(linha)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# mesmo desenho da planilha de alocação (cabeçalho, listas de pessoas à direita, bloco sem posto)
LINHAS = [
    [None, None, "Turno 01", "Turno 02", "Turno 03", None, None, "TURNO 01", None, "TURNO 02"],
    ["CÁLCULO", "Calculo Siol", "Rogerio", None, None, None, None, "JAVA", None, "BACTERIA"],
    [None, "Calculo Optclick 01", "Ramon", "VAGO", None],
    ["BLOCAGEM", "PRA 01", "Ryan", None, None],
    [None, "PRA 02", "Parada", None, None],
    [None, "PRA 03", "VAGO", None, None],
    [None, "PRA 01", "Marcos", None, None],  # repetido no bloco
    [None, None, None, None, None],
    ["Spin", None, "VAGO", "Reserva", None],
]


def _colab(mat, nome, setor, turno="TURNO_1", **kw):
    return Colaborador.objects.create(matricula=mat, nome_completo=nome, grupo="M", setor=setor, turno=turno, **kw)


class LeitorPlanilhaTests(TestCase):
    def test_estrutura_e_situacoes(self):
        d = ler_planilha(xlsx_bytes(LINHAS))
        self.assertEqual([b["nome"] for b in d["blocos"]], ["CÁLCULO", "BLOCAGEM", "Spin"])
        self.assertEqual(d["turnos"], ["TURNO_1", "TURNO_2", "TURNO_3"])
        calc = d["blocos"][0]["postos"]
        self.assertEqual([p["nome"] for p in calc], ["Calculo Siol", "Calculo Optclick 01"])
        self.assertEqual(calc[0]["turnos"]["TURNO_1"], {"original": "Rogerio", "situacao": "ATIVO", "pessoa": "Rogerio"})
        self.assertEqual(calc[1]["turnos"]["TURNO_2"]["situacao"], "VAGO")
        blocagem = d["blocos"][1]["postos"]
        self.assertEqual(blocagem[1]["turnos"]["TURNO_1"]["situacao"], "PARADO")
        self.assertEqual(blocagem[2]["turnos"]["TURNO_1"]["situacao"], "VAGO")
        # posto repetido ignorado com aviso; lista de pessoas à direita não vira turno
        self.assertEqual(len(blocagem), 3)
        self.assertTrue(any("repetido" in a for a in d["avisos"]))
        spin = d["blocos"][2]["postos"]
        self.assertEqual([p["nome"] for p in spin], ["Spin"])  # bloco sem posto vira posto de mesmo nome
        self.assertEqual(spin[0]["turnos"]["TURNO_2"]["situacao"], "RESERVA")

    def test_planilha_invalida(self):
        with self.assertRaises(PlanilhaInvalida):
            ler_planilha(xlsx_bytes([["a", "b"], ["c", "d"]]))
        with self.assertRaises(PlanilhaInvalida):
            ler_planilha(io.BytesIO(b"nao e xlsx"))


class ImportacaoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(self.admin)
        self.setor = Setor.objects.create(nome="Laboratório")  # cadastro (colaboradores)
        self.setor_eq = SetorEquipe.objects.create(nome="Laboratório")  # setor da estrutura
        self.rogerio = _colab("1", "Rogerio Silva", self.setor)
        self.ramon = _colab("2", "Ramon Souza", self.setor)
        self.ryan = _colab("3", "Ryan Lima", self.setor)

    def previa(self, linhas=LINHAS, setor_id=None, nome="p.xlsx"):
        arq = SimpleUploadedFile(nome, xlsx_bytes(linhas).read())
        data = {"arquivo": arq}
        if setor_id is not None:
            data["setor_id"] = setor_id
        return self.client.post(reverse("rh:api_importar_estrutura_equipes_previa"), data)

    def confirmar(self, payload):
        return self.client.post(reverse("rh:api_importar_estrutura_equipes_confirmar"), json.dumps(payload), content_type="application/json")

    def test_pagina_e_previa_nao_gravam(self):
        self.assertEqual(self.client.get(reverse("rh:importar_estrutura_equipes")).status_code, 200)
        r = self.previa(setor_id=self.setor_eq.id)
        self.assertEqual(r.status_code, 200, r.content)
        j = r.json()
        cel = j["blocos"][0]["postos"][0]["turnos"]["TURNO_1"]
        self.assertEqual(cel["decisao"], f"c:{self.rogerio.id}")  # único candidato => sugerido
        self.assertEqual(cel["status"], "ok")
        self.assertEqual(j["blocos"][0]["existe"], False)
        self.assertEqual(GrupoEquipe.objects.count(), 0)
        self.assertEqual(AlocacaoPosto.objects.count(), 0)

    def test_nome_ambiguo_e_nao_encontrado_ficam_para_revisao(self):
        _colab("9", "Rogerio Alves", Setor.objects.create(nome="Outro"))
        _colab("10", "Rogerio Costa", self.setor, turno="TURNO_2")
        linhas = [[None, None, "Turno 01"], ["B", "P1", "Rogerio"], [None, "P2", "Fulano Inexistente"]]
        j = self.previa(linhas, setor_id=self.setor_eq.id).json()
        amb = j["blocos"][0]["postos"][0]["turnos"]["TURNO_1"]
        self.assertEqual((amb["status"], amb["decisao"]), ("ambiguo", ""))  # 2 no setor + 1 fora
        self.assertGreaterEqual(len(amb["candidatos"]), 3)
        nao = j["blocos"][0]["postos"][1]["turnos"]["TURNO_1"]
        self.assertEqual((nao["status"], nao["candidatos"]), ("nao_encontrado", []))

    def payload(self, **extra):
        base = {
            "setor_id": self.setor_eq.id,
            "blocos": [
                {"nome": "CÁLCULO", "postos": [
                    {"nome": "Calculo Siol", "turnos": [{"turno": "TURNO_1", "decisao": f"c:{self.rogerio.id}"}, {"turno": "TURNO_2", "decisao": "s:VAGO"}]},
                    {"nome": "Optclick", "turnos": [{"turno": "TURNO_1", "decisao": f"c:{self.ramon.id}"}]},
                ]},
                {"nome": "BLOCAGEM", "postos": [
                    {"nome": "PRA 01", "turnos": [{"turno": "TURNO_1", "decisao": "s:RESERVA"}]},
                ]},
            ],
        }
        base.update(extra)
        return base

    def test_confirmar_grava_tudo(self):
        r = self.confirmar(self.payload())
        self.assertEqual(r.status_code, 200, r.content)
        res = r.json()["resumo"]
        self.assertEqual((res["blocos_criados"], res["postos_criados"], res["colaboradores"], res["vagos"], res["reservas"]), (2, 3, 2, 1, 1))
        siol = GrupoEquipe.objects.get(nome="Calculo Siol")
        self.assertEqual((siol.parent.nome, siol.setor_estrutura_id), ("CÁLCULO", self.setor_eq.id))
        t1 = AlocacaoPosto.objects.get(posto=siol, turno="TURNO_1")
        self.assertEqual((t1.tipo, t1.colaborador_id), ("PESSOA", self.rogerio.id))
        t2 = AlocacaoPosto.objects.get(posto=siol, turno="TURNO_2")
        self.assertEqual((t2.tipo, t2.colaborador_id), ("VAGO", None))
        self.assertEqual(AlocacaoPosto.objects.get(posto__nome="PRA 01").tipo, "RESERVA")

    def test_reimportar_nao_duplica_e_parado_inativa_o_posto(self):
        self.confirmar(self.payload())
        r = self.confirmar(self.payload())
        res = r.json()["resumo"]
        self.assertEqual((res["blocos_criados"], res["postos_criados"], res["postos_atualizados"], res["colaboradores"], res["vagos"], res["reservas"]), (0, 0, 3, 0, 0, 0))
        self.assertEqual(AlocacaoPosto.objects.count(), 4)
        p = self.payload()
        p["blocos"][1]["postos"][0]["turnos"] = [{"turno": "TURNO_1", "decisao": "s:PARADO"}]
        res = self.confirmar(p).json()["resumo"]
        self.assertEqual(res["postos_parados"], 1)
        self.assertFalse(GrupoEquipe.objects.get(nome="PRA 01").ativo)

    def test_confirmar_exige_decisao_e_e_tudo_ou_nada(self):
        p = self.payload()
        p["blocos"][1]["postos"][0]["turnos"][0]["decisao"] = ""
        r = self.confirmar(p)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(GrupoEquipe.objects.count(), 0)
        p["blocos"][1]["postos"][0]["turnos"][0]["decisao"] = "c:999999"
        self.assertEqual(self.confirmar(p).status_code, 400)
        self.assertEqual(GrupoEquipe.objects.count(), 0)

    def test_setor_novo_e_mesmo_bloco_em_outro_setor(self):
        r = self.confirmar(self.payload(setor_id=None, setor_novo="Produção"))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(SetorEquipe.objects.filter(nome="Produção").exists())
        self.assertFalse(Setor.objects.filter(nome="Produção").exists())  # o cadastro da empresa não é tocado
        # o mesmo nome de bloco em outro setor é um bloco diferente (não move nem reaproveita o existente)
        outro = SetorEquipe.objects.create(nome="Outro")
        r = self.confirmar(self.payload(setor_id=outro.id))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["resumo"]["blocos_criados"], 2)
        self.assertEqual(GrupoEquipe.objects.filter(parent__isnull=True, nome="CÁLCULO").count(), 2)

    def test_validacoes_de_arquivo_e_permissao(self):
        r = self.previa(nome="dados.csv")
        self.assertEqual(r.status_code, 400)
        u = User.objects.create_user("u", "u@u.com", "x")
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("rh:importar_estrutura_equipes")).status_code, 403)
        self.assertEqual(self.previa().status_code, 403)
        self.assertEqual(self.confirmar(self.payload()).status_code, 403)
