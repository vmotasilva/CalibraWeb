import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from organization.models import AlocacaoPosto, GrupoEquipe, Setor, SetorEquipe, TurnoEquipe
from rh.models import Colaborador

PADRAO = ("Administrativo", "Turno 01", "Turno 02", "Turno 03")


def _colab(mat, nome, turno="TURNO_1", setor=None, **kw):
    setor = setor or Setor.objects.get_or_create(nome="Cadastro")[0]
    return Colaborador.objects.create(matricula=mat, nome_completo=nome, grupo="MACRO", setor=setor, turno=turno, **kw)


class Base(TestCase):
    """Utilitários: o usuário cria setores (com os seus turnos), blocos e postos pela API."""

    def setUp(self):
        self.client.force_login(User.objects.create_superuser("adm", "a@a.com", "x"))
        self.turnos = {}  # (nome do setor, nome do turno) -> id

    def post(self, name, payload):
        return self.client.post(reverse(f"rh:{name}"), json.dumps(payload), content_type="application/json")

    def setor(self, nome="Laboratório", turnos=PADRAO):
        r = self.post("api_estrutura_equipes_setor_criar", {"nome": nome, "turnos": [{"nome": t} for t in turnos]})
        self.assertEqual(r.status_code, 200, r.content)
        for t in r.json()["turnos"]:
            self.turnos[(nome, t["nome"])] = t["id"]
        return r.json()["id"]

    def bloco(self, nome="Blocagem", setor_id=None):
        r = self.post("api_estrutura_equipes_salvar", {"nome": nome, "setor_id": setor_id or self.setor(f"S-{nome}")})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["id"]

    def posto(self, nome="PRA 01", bloco_id=None):
        r = self.post("api_estrutura_equipes_salvar", {"nome": nome, "parent_id": bloco_id or self.bloco()})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["id"]

    def alocar(self, posto_id, turno_ids, tipo="VAGO", **extra):
        return self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": posto_id, "turno_ids": turno_ids, "tipo": tipo, **extra})

    def tid(self, setor_id, nome):
        return TurnoEquipe.objects.get(setor_id=setor_id, nome=nome).id


class EstruturaTests(Base):
    def test_pagina_carrega(self):
        r = self.client.get(reverse("rh:estrutura_equipes"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Novo setor")
        self.assertNotContains(r, "12x36")

    def test_construcao_livre_setor_bloco_posto(self):
        sid = self.setor("Laboratório")
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {"nome": "laboratório"}).status_code, 400)  # duplicado
        bid = self.bloco("Blocagem", sid)
        pid = self.posto("PRA 01", bid)
        d = self.client.get(reverse("rh:api_estrutura_equipes_dados")).json()
        lab = next(s for s in d["setores"] if s["id"] == sid)
        self.assertEqual(sorted(t["nome"] for t in lab["turnos"]), sorted(PADRAO))
        posto = next(g for g in d["grupos"] if g["id"] == pid)
        self.assertEqual((posto["parent_id"], posto["nivel"], posto["setor_id"]), (bid, 2, sid))
        self.assertNotIn("turnos", d)  # não existe lista global de turnos: cada setor tem os seus

    def test_regras_de_estrutura(self):
        sid = self.setor()
        bid = self.bloco("A", sid)
        pid = self.posto("P", bid)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "Sem setor"}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "X", "parent_id": pid}).status_code, 400)  # posto em posto
        outro = self.bloco("B", sid)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"id": bid, "nome": "A", "parent_id": outro}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "a", "setor_id": sid}).status_code, 400)  # nome repetido no setor
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "A", "setor_id": self.setor("Outro")}).status_code, 200)
        novo = self.setor("Novo")
        self.post("api_estrutura_equipes_salvar", {"id": bid, "nome": "A", "setor_id": novo})
        self.assertEqual(GrupoEquipe.objects.get(pk=pid).setor_estrutura_id, novo)  # posto herda o setor

    def test_editar_sem_informar_ordem_nao_zera(self):
        sid = self.setor()
        bid = self.post("api_estrutura_equipes_salvar", {"nome": "B", "setor_id": sid, "ordem": 7}).json()["id"]
        self.post("api_estrutura_equipes_salvar", {"id": bid, "nome": "B2", "setor_id": sid})
        self.assertEqual(GrupoEquipe.objects.get(pk=bid).ordem, 7)

    def test_excluir_bloco_so_sem_postos_e_posto_remove_alocacoes(self):
        bid = self.bloco("Bloco")
        pid = self.posto("Posto", bid)
        sid = GrupoEquipe.objects.get(pk=bid).setor_estrutura_id
        self.alocar(pid, [self.tid(sid, "Turno 01")], "RESERVA")
        self.assertEqual(self.post("api_estrutura_equipes_excluir", {"id": bid}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_excluir", {"id": pid}).json()["alocacoes_removidas"], 1)
        self.assertEqual(self.post("api_estrutura_equipes_excluir", {"id": bid}).status_code, 200)

    def test_usuario_sem_permissao(self):
        self.client.force_login(User.objects.create_user("u", "u@u.com", "x"))
        self.assertEqual(self.client.get(reverse("rh:estrutura_equipes")).status_code, 403)
        self.assertEqual(self.client.get(reverse("rh:api_estrutura_equipes_dados")).status_code, 403)
        for nome in ("api_estrutura_equipes_setor_criar", "api_estrutura_equipes_salvar", "api_estrutura_equipes_alocacoes_criar", "api_estrutura_equipes_setor_excluir"):
            self.assertEqual(self.post(nome, {"nome": "X"}).status_code, 403)


class TurnosPorSetorTests(Base):
    """Cada setor define os próprios turnos (cadastro desta tela, independente de outros módulos)."""

    def test_setor_com_turnos_proprios(self):
        a = self.setor("Montagem", ("1º Turno", "2º Turno"))
        b = self.setor("Expedição", ("Manhã", "Tarde", "Noite"))
        d = self.client.get(reverse("rh:api_estrutura_equipes_dados")).json()
        por = {s["nome"]: sorted(t["nome"] for t in s["turnos"]) for s in d["setores"]}
        self.assertEqual(por["Montagem"], ["1º Turno", "2º Turno"])
        self.assertEqual(por["Expedição"], ["Manhã", "Noite", "Tarde"])
        self.assertNotEqual(a, b)

    def test_mesmo_nome_de_turno_em_setores_diferentes(self):
        self.setor("A", ("Turno 01",))
        self.setor("B", ("Turno 01",))
        self.assertEqual(TurnoEquipe.objects.filter(nome="Turno 01").count(), 2)

    def test_validacoes_dos_turnos(self):
        base = {"nome": "S"}
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {**base, "turnos": [{"nome": "A"}, {"nome": "a "}]}).status_code, 400)  # repetido
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {**base, "turnos": [{"nome": "  "}]}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {**base, "turnos": [{"nome": "x" * 51}]}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {**base, "turnos": [{"nome": f"T{i}"} for i in range(13)]}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {**base, "turnos": "Turno 01"}).status_code, 400)
        self.assertFalse(SetorEquipe.objects.filter(nome="S").exists())  # nada é criado se os turnos são inválidos
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {**base, "turnos": []}).status_code, 200)  # setor sem turnos é permitido

    def test_editar_turnos_renomear_adicionar_remover(self):
        sid = self.setor("S", ("Turno 01", "Turno 02"))
        t1, t2 = self.turnos[("S", "Turno 01")], self.turnos[("S", "Turno 02")]
        r = self.post("api_estrutura_equipes_setor_criar", {"id": sid, "nome": "S", "turnos": [{"id": t1, "nome": "Manhã"}, {"nome": "Noite"}]})
        self.assertEqual(r.status_code, 200, r.content)
        nomes = {t["id"]: t["nome"] for t in r.json()["turnos"]}
        self.assertEqual(nomes[t1], "Manhã")  # renomear mantém o id (e as alocações)
        self.assertNotIn(t2, nomes)  # removido (sem alocações)
        self.assertEqual(sorted(nomes.values()), ["Manhã", "Noite"])
        # trocar os nomes entre dois turnos não conflita
        ids = {n: i for i, n in nomes.items()}
        r = self.post("api_estrutura_equipes_setor_criar", {"id": sid, "nome": "S", "turnos": [{"id": ids["Manhã"], "nome": "Noite"}, {"id": ids["Noite"], "nome": "Manhã"}]})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(TurnoEquipe.objects.get(pk=ids["Manhã"]).nome, "Noite")
        # sem a chave "turnos" na edição, os turnos não mudam
        self.post("api_estrutura_equipes_setor_criar", {"id": sid, "nome": "S novo"})
        self.assertEqual(TurnoEquipe.objects.filter(setor_id=sid).count(), 2)

    def test_nao_remove_turno_com_alocacoes(self):
        sid = self.setor("S", ("Turno 01", "Turno 02"))
        pid = self.posto("P", self.bloco("B", sid))
        t1, t2 = self.turnos[("S", "Turno 01")], self.turnos[("S", "Turno 02")]
        self.alocar(pid, [t2], "VAGO")
        r = self.post("api_estrutura_equipes_setor_criar", {"id": sid, "nome": "S", "turnos": [{"id": t1, "nome": "Turno 01"}]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Turno 02", r.json()["error"])
        self.assertTrue(TurnoEquipe.objects.filter(pk=t2).exists())

    def test_turno_de_outro_setor_e_rejeitado(self):
        s1 = self.setor("S1", ("Turno 01",))
        s2 = self.setor("S2", ("Turno 01",))
        pid = self.posto("P", self.bloco("B", s1))
        outro = self.turnos[("S2", "Turno 01")]
        self.assertEqual(self.alocar(pid, [outro]).status_code, 400)
        self.assertEqual(self.alocar(pid, [self.turnos[("S1", "Turno 01")]]).status_code, 200)
        self.assertEqual(self.alocar(pid, []).status_code, 400)
        self.assertEqual(self.alocar(pid, [999999]).status_code, 400)
        self.assertEqual(AlocacaoPosto.objects.count(), 1)
        self.assertNotEqual(s1, s2)

    def test_setor_sem_turnos_nao_recebe_alocacao(self):
        pid = self.posto("P", self.bloco("B", self.setor("Vazio", ())))
        self.assertEqual(self.alocar(pid, [1]).status_code, 400)


class AlocacoesTests(Base):
    def setUp(self):
        super().setUp()
        self.sid = self.setor("Lab")
        self.pid = self.posto("P", self.bloco("B", self.sid))
        self.t = {n: self.turnos[("Lab", n)] for n in PADRAO}
        self.a = _colab("1", "Ana")
        self.b = _colab("2", "Bia")

    def test_colaboradores_em_varios_turnos(self):
        j = self.alocar(self.pid, [self.t["Turno 01"], self.t["Turno 02"], self.t["Turno 02"]], "PESSOA", colaborador_ids=[self.a.id, self.b.id]).json()
        self.assertEqual((j["criadas"], j["ja_existiam"], j["turnos"]), (4, 0, 2))
        j = self.alocar(self.pid, [self.t["Turno 01"], self.t["Turno 03"]], "PESSOA", colaborador_ids=[self.a.id]).json()
        self.assertEqual((j["criadas"], j["ja_existiam"]), (1, 1))
        self.assertEqual(AlocacaoPosto.objects.filter(colaborador=self.a).count(), 3)

    def test_mesmo_colaborador_em_varios_postos(self):
        outro = self.posto("P2", GrupoEquipe.objects.get(pk=self.pid).parent_id)
        self.alocar(self.pid, [self.t["Turno 01"]], "PESSOA", colaborador_ids=[self.a.id])
        self.alocar(outro, [self.t["Turno 01"]], "PESSOA", colaborador_ids=[self.a.id])
        self.assertEqual(AlocacaoPosto.objects.filter(colaborador=self.a).count(), 2)

    def test_vagos_e_reservas_por_turno(self):
        j = self.alocar(self.pid, [self.t["Administrativo"], self.t["Turno 01"], self.t["Turno 02"]], "VAGO", quantidade=2).json()
        self.assertEqual(j["criadas"], 6)
        self.alocar(self.pid, [self.t["Turno 03"]], "RESERVA")
        t3 = AlocacaoPosto.objects.filter(posto_id=self.pid, turno_estrutura_id=self.t["Turno 03"])
        self.assertEqual((t3.count(), t3.first().tipo, t3.first().colaborador_id), (1, "RESERVA", None))
        d = self.client.get(reverse("rh:api_estrutura_equipes_dados")).json()
        self.assertEqual(len([x for x in d["alocacoes"] if x["posto_id"] == self.pid]), 7)
        self.assertTrue(all("turno_id" in x for x in d["alocacoes"]))

    def test_validacoes(self):
        t1 = self.t["Turno 01"]
        bloco = GrupoEquipe.objects.get(pk=self.pid).parent_id
        self.assertEqual(self.alocar(bloco, [t1]).status_code, 400)  # bloco não recebe
        self.assertEqual(self.alocar(self.pid, [t1], "VAGO", quantidade=99).status_code, 400)
        self.assertEqual(self.alocar(self.pid, [t1], "PESSOA").status_code, 400)  # sem colaborador
        self.assertEqual(self.alocar(self.pid, [t1], "PESSOA", colaborador_ids=[999999]).status_code, 400)
        self.a.is_active = False
        self.a.save()
        self.assertEqual(self.alocar(self.pid, [t1], "PESSOA", colaborador_ids=[self.a.id]).status_code, 400)
        self.assertEqual(AlocacaoPosto.objects.count(), 0)

    def test_contratar_mover_e_remover(self):
        p2 = self.posto("P2", GrupoEquipe.objects.get(pk=self.pid).parent_id)
        self.alocar(self.pid, [self.t["Turno 01"]], "VAGO")
        vaga = AlocacaoPosto.objects.get(posto_id=self.pid)
        novo = _colab("5", "Contratado Novo")
        r = self.post("api_estrutura_equipes_alocacoes_atualizar", {"id": vaga.id, "tipo": "PESSOA", "colaborador_id": novo.id, "posto_id": p2, "turno_id": self.t["Turno 02"]})
        self.assertEqual(r.status_code, 200, r.content)
        vaga.refresh_from_db()
        self.assertEqual((vaga.tipo, vaga.colaborador_id, vaga.posto_id, vaga.turno_estrutura_id), ("PESSOA", novo.id, p2, self.t["Turno 02"]))
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_atualizar", {"id": vaga.id, "colaborador_id": None}).status_code, 400)
        self.post("api_estrutura_equipes_alocacoes_atualizar", {"id": vaga.id, "tipo": "VAGO"})
        vaga.refresh_from_db()
        self.assertEqual((vaga.tipo, vaga.colaborador_id), ("VAGO", None))
        # turno de outro setor não vale
        outro = self.setor("Outro", ("Turno X",))
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_atualizar", {"id": vaga.id, "turno_id": self.turnos[("Outro", "Turno X")]}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_excluir", {"ids": [vaga.id]}).json()["removidas"], 1)
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_excluir", {"ids": []}).status_code, 400)
        self.assertNotEqual(outro, self.sid)

    def test_mover_para_posto_de_outro_setor_exige_turno_do_setor(self):
        s2 = self.setor("S2", ("Turno 01",))
        p2 = self.posto("Q", self.bloco("B2", s2))
        self.alocar(self.pid, [self.t["Turno 01"]], "VAGO")
        aloc = AlocacaoPosto.objects.get(posto_id=self.pid)
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_atualizar", {"id": aloc.id, "posto_id": p2}).status_code, 400)
        ok = self.post("api_estrutura_equipes_alocacoes_atualizar", {"id": aloc.id, "posto_id": p2, "turno_id": self.turnos[("S2", "Turno 01")]})
        self.assertEqual(ok.status_code, 200, ok.content)

    def test_busca_de_colaboradores(self):
        c = _colab("7", "Maria Joaquina")
        _colab("8", "Outro Nome")
        self.alocar(self.pid, [self.t["Turno 01"]], "PESSOA", colaborador_ids=[c.id])
        j = self.client.get(reverse("rh:api_estrutura_equipes_membros"), {"q": "maria"}).json()
        self.assertEqual([m["nome"] for m in j["membros"]], ["Maria Joaquina"])
        self.assertEqual(j["membros"][0]["postos"], ["B › P"])


class ColaboradoresNaTelaTests(Base):
    def setUp(self):
        super().setUp()
        self.s1 = Setor.objects.create(nome="Laboratório")  # cadastro da empresa
        self.s2 = Setor.objects.create(nome="Qualidade")

    def test_filtros_de_setor_do_cadastro_sem_posto_e_limite(self):
        a = _colab("1", "Ana Lab", setor=self.s1)
        _colab("2", "Bia Lab", "12X36", setor=self.s1)  # o cadastro de pessoas pode ter outros turnos
        _colab("3", "Caio Qual", setor=self.s2)
        sid = self.setor("Estrutura")
        pid = self.posto("P", self.bloco("B", sid))
        self.alocar(pid, [self.turnos[("Estrutura", "Turno 01")]], "PESSOA", colaborador_ids=[a.id])
        url = reverse("rh:api_estrutura_equipes_membros")
        nomes = lambda **p: [m["nome"] for m in self.client.get(url, p).json()["membros"]]
        self.assertEqual(nomes(setor_cadastro_id=self.s1.id), ["Ana Lab", "Bia Lab"])
        self.assertEqual(nomes(setor_cadastro_id=self.s2.id), ["Caio Qual"])
        self.assertEqual(nomes(setor_cadastro_id=self.s1.id, sem_posto="1"), ["Bia Lab"])
        self.assertEqual(nomes(turno="12X36"), ["Bia Lab"])
        j = self.client.get(url, {"limite": 1}).json()
        self.assertEqual((len(j["membros"]), j["total"], j["truncado"]), (1, 3, True))
        self.assertEqual(self.client.get(url, {"setor_cadastro_id": "abc"}).status_code, 400)
        self.assertEqual(self.client.get(url, {"limite": "9999"}).status_code, 200)

    def test_paginacao_filtros_lider_cargo_e_opcoes(self):
        lider = _colab("90", "Zeca Líder", setor=self.s1, cargo="SUPERVISOR")
        for i in range(7):
            _colab(f"1{i}", f"Pessoa {i}", setor=self.s1, cargo="AUXILIAR", lider=lider)
        url = reverse("rh:api_estrutura_equipes_membros")
        j = self.client.get(url, {"pagina": 2, "por_pagina": 3, "lider_id": lider.id, "opcoes": 1}).json()
        self.assertEqual((j["total"], j["paginas"], j["pagina"], j["truncado"]), (7, 3, 2, False))
        self.assertEqual([m["nome"] for m in j["membros"]], ["Pessoa 3", "Pessoa 4", "Pessoa 5"])
        self.assertIn(lider.id, [x["id"] for x in j["opcoes"]["lideres"]])
        self.assertIn("AUXILIAR", j["opcoes"]["cargos"])
        self.assertTrue(j["opcoes"]["setores"] and j["opcoes"]["turnos"])
        j = self.client.get(url, {"pagina": 99, "por_pagina": 3, "lider_id": lider.id}).json()
        self.assertEqual((j["pagina"], len(j["membros"])), (3, 1))  # página além do fim vai para a última
        self.assertEqual(self.client.get(url, {"cargo": "SUPERVISOR"}).json()["total"], 1)
        self.assertEqual(self.client.get(url, {"pagina": "x"}).status_code, 400)

    def test_alocar_varios_de_uma_vez(self):
        cs = [_colab(str(i), f"Pessoa {i}", setor=self.s1) for i in range(5)]
        sid = self.setor("E")
        pid = self.posto("P", self.bloco("B", sid))
        r = self.alocar(pid, [self.turnos[("E", "Turno 02")]], "PESSOA", colaborador_ids=[c.id for c in cs])
        self.assertEqual(r.json()["criadas"], 5)


class SetoresIndependentesTests(Base):
    """Os setores da estrutura são um cadastro próprio, independente do cadastro de setores da empresa."""

    def test_tela_nao_lista_setores_do_cadastro_da_empresa(self):
        Setor.objects.create(nome="ALMOXARIFADO")
        Setor.objects.create(nome="ATENDIMENTO")
        d = self.client.get(reverse("rh:api_estrutura_equipes_dados")).json()
        self.assertEqual(d["setores"], [])
        self.assertEqual(sorted(x["nome"] for x in d["setores_cadastro"]), ["ALMOXARIFADO", "ATENDIMENTO"])

    def test_criar_e_renomear_nao_toca_no_cadastro_da_empresa(self):
        reg = Setor.objects.create(nome="Qualidade")
        sid = self.setor("Qualidade")  # mesmo nome do cadastro: permitido
        self.assertEqual(Setor.objects.count(), 1)
        r = self.post("api_estrutura_equipes_setor_criar", {"id": sid, "nome": "Qualidade Total"})
        self.assertEqual((r.status_code, r.json()["criado"]), (200, False))
        self.assertEqual(SetorEquipe.objects.get(pk=sid).nome, "Qualidade Total")
        reg.refresh_from_db()
        self.assertEqual(reg.nome, "Qualidade")
        self.setor("Produção")
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {"id": sid, "nome": "produção"}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {"id": sid, "nome": "QUALIDADE TOTAL"}).status_code, 200)
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {"id": 999999, "nome": "X"}).status_code, 404)
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {"id": sid, "nome": "  "}).status_code, 400)

    def test_excluir_setor_so_sem_blocos_e_leva_os_turnos(self):
        reg = Setor.objects.create(nome="Do cadastro")
        sid = self.setor("Vazio")
        com = self.setor("Com bloco")
        self.post("api_estrutura_equipes_salvar", {"nome": "B", "setor_id": com})
        self.assertEqual(self.post("api_estrutura_equipes_setor_excluir", {"id": com}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_setor_excluir", {"id": sid}).status_code, 200)
        self.assertFalse(SetorEquipe.objects.filter(pk=sid).exists())
        self.assertFalse(TurnoEquipe.objects.filter(setor_id=sid).exists())
        self.assertEqual(self.post("api_estrutura_equipes_setor_excluir", {"id": 999999}).status_code, 404)
        self.assertTrue(Setor.objects.filter(pk=reg.pk).exists())

    def test_bloco_exige_setor_da_estrutura(self):
        reg = Setor.objects.create(nome="Só no cadastro")
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "B", "setor_id": reg.id}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "B"}).status_code, 400)


class MigracaoDadosAntigosTests(TestCase):
    """Migrações de dados: organization.0005 (grupo/posto antigos), 0007 (setores) e 0009 (turnos por setor)."""

    def test_0005_copia_e_e_idempotente(self):
        import importlib

        from django.apps import apps

        from organization.models import GrupoEquipeTurno

        migracao = importlib.import_module("organization.migrations.0005_alocacao_posto")
        setor = Setor.objects.create(nome="S")
        bloco = GrupoEquipe.objects.create(nome="B", setor=setor)
        posto = GrupoEquipe.objects.create(nome="P", parent=bloco)
        a, b = _colab("1", "Ana"), _colab("2", "Bia", turno="TURNO_2")
        GrupoEquipeTurno.objects.create(grupo=posto, turno="TURNO_1", responsavel=a, situacao="ATIVO")
        GrupoEquipeTurno.objects.create(grupo=posto, turno="TURNO_2", situacao="VAGO")
        GrupoEquipeTurno.objects.create(grupo=posto, turno="TURNO_3", situacao="RESERVA")
        GrupoEquipeTurno.objects.create(grupo=posto, turno="ADM", situacao="PARADO")  # não é migrado
        Colaborador.objects.filter(pk=b.pk).update(equipe=posto)
        for _ in range(2):
            migracao.copiar_dados_antigos(apps, None)
        rows = {(x.turno, x.tipo, x.colaborador_id) for x in AlocacaoPosto.objects.filter(posto=posto)}
        self.assertEqual(rows, {("TURNO_1", "PESSOA", a.id), ("TURNO_2", "VAGO", None), ("TURNO_3", "RESERVA", None), ("TURNO_2", "PESSOA", b.id)})

    def test_0007_copia_so_setores_com_blocos(self):
        import importlib

        from django.apps import apps

        migracao = importlib.import_module("organization.migrations.0007_copiar_setores_equipe")
        usado = Setor.objects.create(nome="SURFAÇAGEM")
        Setor.objects.create(nome="ALMOXARIFADO")
        bloco = GrupoEquipe.objects.create(nome="Corte", setor=usado)
        posto = GrupoEquipe.objects.create(nome="VFT 01", parent=bloco)
        for _ in range(2):
            migracao.copiar_setores(apps, None)
        self.assertEqual(list(SetorEquipe.objects.values_list("nome", flat=True)), ["SURFAÇAGEM"])
        bloco.refresh_from_db()
        posto.refresh_from_db()
        self.assertEqual(posto.setor_estrutura_id, bloco.setor_estrutura_id)

    def test_0009_cria_turnos_por_setor_e_liga_as_alocacoes(self):
        import importlib

        from django.apps import apps

        migracao = importlib.import_module("organization.migrations.0009_copiar_turnos_equipe")
        setor = SetorEquipe.objects.create(nome="S")
        bloco = GrupoEquipe.objects.create(nome="B", setor_estrutura=setor)
        posto = GrupoEquipe.objects.create(nome="P", parent=bloco)
        c = _colab("1", "Ana")
        antigas = [
            AlocacaoPosto.objects.create(posto=posto, turno="TURNO_2", tipo="PESSOA", colaborador=c),
            AlocacaoPosto.objects.create(posto=posto, turno="ADM", tipo="VAGO"),
            AlocacaoPosto.objects.create(posto=posto, turno="12X36", tipo="RESERVA"),
        ]
        for _ in range(2):  # idempotente
            migracao.copiar_turnos(apps, None)
        self.assertEqual(sorted(TurnoEquipe.objects.filter(setor=setor).values_list("nome", flat=True)), ["12x36", "Administrativo", "Turno 01", "Turno 02", "Turno 03"])
        nomes = [AlocacaoPosto.objects.get(pk=a.pk).turno_estrutura.nome for a in antigas]
        self.assertEqual(nomes, ["Turno 02", "Administrativo", "12x36"])
        self.assertEqual(AlocacaoPosto.objects.count(), 3)


class ExportacaoExcelTests(Base):
    def setUp(self):
        super().setUp()
        self.sa = self.setor("Laboratório: A/B")
        self.sb = self.setor("Qualidade")
        self.pa = self.posto("PRA 01", self.bloco("Blocagem", self.sa))
        self.pb = self.posto("Inspeção", self.bloco("Auditoria", self.sb))
        ana = _colab("1", "Ana Souza")
        self.alocar(self.pa, [self.turnos[("Laboratório: A/B", "Turno 01")]], "PESSOA", colaborador_ids=[ana.id])
        self.alocar(self.pa, [self.turnos[("Laboratório: A/B", "Turno 02")]], "VAGO", quantidade=2, observacao="contratar")
        self.alocar(self.pb, [self.turnos[("Qualidade", "Turno 01")]], "RESERVA")

    def _wb(self, **params):
        from io import BytesIO

        from openpyxl import load_workbook

        r = self.client.get(reverse("rh:exportar_estrutura_equipes"), params)
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertIn("spreadsheetml", r["Content-Type"])
        return load_workbook(BytesIO(r.content)), r

    def test_uma_aba_por_setor_com_nomes_validos(self):
        wb, r = self._wb()
        self.assertEqual(wb.sheetnames, ["Laboratório A B", "Qualidade"])  # ':' e '/' viram espaço
        self.assertIn("estrutura_equipes_", r["Content-Disposition"])

    def test_conteudo_postos_por_bloco_e_turnos_do_setor(self):
        wb, _ = self._wb()
        ws = wb["Laboratório A B"]
        cab = [c.value for c in ws[4]]
        self.assertEqual(cab[:2], ["Bloco", "Posto de trabalho"])
        self.assertIn("Turno 01", cab)
        self.assertEqual((ws["A5"].value, ws["B5"].value), ("Blocagem", "PRA 01"))
        col = {v: i for i, v in enumerate(cab, 1)}
        self.assertEqual(ws.cell(row=5, column=col["Turno 01"]).value, "Ana Souza")
        self.assertEqual(ws.cell(row=5, column=col["Turno 02"]).value, "VAGO (contratar)\nVAGO (contratar)")
        self.assertEqual(ws.cell(row=6, column=col["Turno 01"]).value, "1 pessoa(s) · 0 vaga(s) · 0 reserva(s)")
        self.assertEqual(ws.cell(row=6, column=col["Turno 02"]).value, "0 pessoa(s) · 2 vaga(s) · 0 reserva(s)")
        wq = wb["Qualidade"]
        colq = {c.value: i for i, c in enumerate(wq[4], 1)}
        self.assertEqual(wq.cell(row=5, column=colq["Turno 01"]).value, "RESERVA")

    def test_filtra_por_setor(self):
        wb, r = self._wb(setor=self.sb)
        self.assertEqual(wb.sheetnames, ["Qualidade"])
        self.assertIn("qualidade", r["Content-Disposition"])
        self.assertEqual(self.client.get(reverse("rh:exportar_estrutura_equipes"), {"setor": "abc"}).status_code, 400)
        self.assertEqual(self.client.get(reverse("rh:exportar_estrutura_equipes"), {"setor": "99999"}).status_code, 404)

    def test_sem_permissao(self):
        self.client.force_login(User.objects.create_user("semperm", password="x"))
        self.assertIn(self.client.get(reverse("rh:exportar_estrutura_equipes")).status_code, (302, 403))

