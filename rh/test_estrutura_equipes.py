import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from organization.models import AlocacaoPosto, GrupoEquipe, Setor
from rh.models import Colaborador


def _colab(mat, nome, turno="TURNO_1", **kw):
    setor, _ = Setor.objects.get_or_create(nome="Produção")
    return Colaborador.objects.create(matricula=mat, nome_completo=nome, grupo="MACRO", setor=setor, turno=turno, **kw)


class EstruturaEquipesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(self.admin)

    def post(self, name, payload):
        return self.client.post(reverse(f"rh:{name}"), json.dumps(payload), content_type="application/json")

    def setor(self, nome="Laboratório"):
        r = self.post("api_estrutura_equipes_setor_criar", {"nome": nome})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["id"]

    def bloco(self, nome="Blocagem", setor_id=None):
        r = self.post("api_estrutura_equipes_salvar", {"nome": nome, "setor_id": setor_id or self.setor(f"S-{nome}")})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["id"]

    def posto(self, nome="PRA 01", bloco_id=None):
        r = self.post("api_estrutura_equipes_salvar", {"nome": nome, "parent_id": bloco_id or self.bloco()})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["id"]

    def test_pagina_carrega(self):
        r = self.client.get(reverse("rh:estrutura_equipes"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Novo setor")

    def test_construcao_livre_setor_bloco_posto(self):
        sid = self.setor("Laboratório")
        self.assertEqual(self.post("api_estrutura_equipes_setor_criar", {"nome": "laboratório"}).status_code, 400)  # duplicado
        bid = self.bloco("Blocagem", sid)
        pid = self.posto("PRA 01", bid)
        d = self.client.get(reverse("rh:api_estrutura_equipes_dados")).json()
        self.assertIn("Laboratório", [s["nome"] for s in d["setores"]])
        posto = next(g for g in d["grupos"] if g["id"] == pid)
        self.assertEqual((posto["parent_id"], posto["nivel"], posto["setor_id"]), (bid, 2, sid))

    def test_regras_de_estrutura(self):
        sid = self.setor()
        bid = self.bloco("A", sid)
        pid = self.posto("P", bid)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "Sem setor"}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "X", "parent_id": pid}).status_code, 400)  # posto em posto
        outro = self.bloco("B", sid)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"id": bid, "nome": "A", "parent_id": outro}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "a", "setor_id": sid}).status_code, 400)  # nome repetido no setor
        # mesmo nome de bloco em outro setor é permitido
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "A", "setor_id": self.setor("Outro")}).status_code, 200)
        novo = self.setor("Novo")
        self.post("api_estrutura_equipes_salvar", {"id": bid, "nome": "A", "setor_id": novo})
        self.assertEqual(GrupoEquipe.objects.get(pk=pid).setor_id, novo)  # posto herda o setor

    def test_alocar_colaborador_vago_e_reserva(self):
        pid = self.posto()
        c1, c2 = _colab("1", "Rogerio Silva"), _colab("2", "Ramon Souza")
        r = self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": pid, "turno": "TURNO_1", "tipo": "PESSOA", "colaborador_ids": [c1.id, c2.id]})
        self.assertEqual(r.json()["criadas"], 2)
        # repetir não duplica
        r = self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": pid, "turno": "TURNO_1", "tipo": "PESSOA", "colaborador_ids": [c1.id]})
        self.assertEqual((r.json()["criadas"], r.json()["ja_existiam"]), (0, 1))
        # o mesmo colaborador em outro turno e em outro posto é livre (polivalência)
        self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": pid, "turno": "TURNO_2", "tipo": "PESSOA", "colaborador_ids": [c1.id]})
        outro = self.posto("PRA 02", GrupoEquipe.objects.get(pk=pid).parent_id)
        self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": outro, "turno": "TURNO_1", "tipo": "PESSOA", "colaborador_ids": [c1.id]})
        self.assertEqual(AlocacaoPosto.objects.filter(colaborador=c1).count(), 3)
        # VAGO x2 e RESERVA x1
        self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": pid, "turno": "TURNO_3", "tipo": "VAGO", "quantidade": 2})
        self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": pid, "turno": "TURNO_3", "tipo": "RESERVA"})
        t3 = AlocacaoPosto.objects.filter(posto_id=pid, turno="TURNO_3")
        self.assertEqual((t3.filter(tipo="VAGO").count(), t3.filter(tipo="RESERVA").count()), (2, 1))
        self.assertTrue(all(a.colaborador_id is None for a in t3))
        d = self.client.get(reverse("rh:api_estrutura_equipes_dados")).json()
        self.assertEqual(len([a for a in d["alocacoes"] if a["posto_id"] == pid]), 6)

    def test_validacoes_de_alocacao(self):
        sid = self.setor()
        bid = self.bloco("Bl", sid)
        pid = self.posto("P", bid)
        c = _colab("1", "Ana")
        base = {"turno": "TURNO_1", "tipo": "VAGO"}
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_criar", {**base, "posto_id": bid}).status_code, 400)  # bloco não recebe
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_criar", {**base, "posto_id": pid, "turno": "X"}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_criar", {**base, "posto_id": pid, "quantidade": 99}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_criar", {**base, "posto_id": pid, "tipo": "PESSOA"}).status_code, 400)  # sem colaborador
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_criar", {**base, "posto_id": pid, "tipo": "PESSOA", "colaborador_ids": [999999]}).status_code, 400)
        c.is_active = False
        c.save()
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_criar", {**base, "posto_id": pid, "tipo": "PESSOA", "colaborador_ids": [c.id]}).status_code, 400)

    def test_contratar_mover_e_remover(self):
        p1 = self.posto("P1")
        p2 = self.posto("P2", GrupoEquipe.objects.get(pk=p1).parent_id)
        self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": p1, "turno": "TURNO_1", "tipo": "VAGO"})
        vaga = AlocacaoPosto.objects.get(posto_id=p1)
        novo = _colab("5", "Contratado Novo")
        # VAGO vira colaborador (contratação) e muda de posto/turno
        r = self.post("api_estrutura_equipes_alocacoes_atualizar", {"id": vaga.id, "tipo": "PESSOA", "colaborador_id": novo.id, "posto_id": p2, "turno": "TURNO_2"})
        self.assertEqual(r.status_code, 200, r.content)
        vaga.refresh_from_db()
        self.assertEqual((vaga.tipo, vaga.colaborador_id, vaga.posto_id, vaga.turno), ("PESSOA", novo.id, p2, "TURNO_2"))
        # PESSOA sem colaborador é inválido; volta a VAGO limpa o colaborador
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_atualizar", {"id": vaga.id, "colaborador_id": None}).status_code, 400)
        self.post("api_estrutura_equipes_alocacoes_atualizar", {"id": vaga.id, "tipo": "VAGO"})
        vaga.refresh_from_db()
        self.assertEqual((vaga.tipo, vaga.colaborador_id), ("VAGO", None))
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_excluir", {"ids": [vaga.id]}).json()["removidas"], 1)
        self.assertEqual(self.post("api_estrutura_equipes_alocacoes_excluir", {"ids": []}).status_code, 400)

    def test_busca_de_colaboradores(self):
        pid = self.posto("P")
        c = _colab("7", "Maria Joaquina")
        _colab("8", "Outro Nome")
        self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": pid, "turno": "TURNO_1", "tipo": "PESSOA", "colaborador_ids": [c.id]})
        j = self.client.get(reverse("rh:api_estrutura_equipes_membros"), {"q": "maria"}).json()
        self.assertEqual([m["nome"] for m in j["membros"]], ["Maria Joaquina"])
        self.assertEqual(j["membros"][0]["postos"], ["P"])

    def test_excluir_bloco_so_sem_postos_e_posto_remove_alocacoes(self):
        bid = self.bloco("Bloco")
        pid = self.posto("Posto", bid)
        self.post("api_estrutura_equipes_alocacoes_criar", {"posto_id": pid, "turno": "TURNO_1", "tipo": "RESERVA"})
        self.assertEqual(self.post("api_estrutura_equipes_excluir", {"id": bid}).status_code, 400)
        self.assertEqual(self.post("api_estrutura_equipes_excluir", {"id": pid}).json()["alocacoes_removidas"], 1)
        self.assertEqual(self.post("api_estrutura_equipes_excluir", {"id": bid}).status_code, 200)

    def test_usuario_sem_permissao(self):
        u = User.objects.create_user("u", "u@u.com", "x")
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("rh:estrutura_equipes")).status_code, 403)
        self.assertEqual(self.client.get(reverse("rh:api_estrutura_equipes_dados")).status_code, 403)
        for nome in ("api_estrutura_equipes_setor_criar", "api_estrutura_equipes_salvar", "api_estrutura_equipes_alocacoes_criar"):
            self.assertEqual(self.post(nome, {"nome": "X"}).status_code, 403)


class MigracaoDadosAntigosTests(TestCase):
    """A migração organization.0005 leva GrupoEquipeTurno e Colaborador.equipe para AlocacaoPosto."""

    def test_copia_e_e_idempotente(self):
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
        for _ in range(2):  # rodar duas vezes não duplica
            migracao.copiar_dados_antigos(apps, None)
        rows = {(x.turno, x.tipo, x.colaborador_id) for x in AlocacaoPosto.objects.filter(posto=posto)}
        self.assertEqual(rows, {("TURNO_1", "PESSOA", a.id), ("TURNO_2", "VAGO", None), ("TURNO_3", "RESERVA", None), ("TURNO_2", "PESSOA", b.id)})
