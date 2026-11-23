import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from organization.models import GrupoEquipe, GrupoEquipeTurno, Setor
from rh.models import Colaborador


def _colab(mat, nome, turno="TURNO_1", **kw):
    setor, _ = Setor.objects.get_or_create(nome="Produção")
    return Colaborador.objects.create(
        matricula=mat, nome_completo=nome, grupo="MACRO", setor=setor, turno=turno, **kw
    )


class EstruturaEquipesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(self.admin)

    def post(self, name, payload):
        return self.client.post(reverse(f"rh:{name}"), json.dumps(payload), content_type="application/json")

    def setor(self, nome="Produção"):
        return Setor.objects.get_or_create(nome=nome)[0]

    def criar(self, nome, parent=None, **extra):
        if parent is None:
            extra.setdefault("setor_id", self.setor().id)
        r = self.post("api_estrutura_equipes_salvar", {"nome": nome, "parent_id": parent, **extra})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["id"]

    def test_pagina_carrega(self):
        r = self.client.get(reverse("rh:estrutura_equipes"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Estrutura de Equipes e Turnos")

    def test_setor_bloco_posto_e_situacoes(self):
        resp = _colab("1", "Rogerio Silva")
        bloco = self.criar("Blocagem")
        posto = self.criar(
            "PRA 01", bloco,
            turnos=[
                {"turno": "TURNO_1", "responsavel_id": resp.id, "situacao": "ATIVO", "efetivo_planejado": 1},
                {"turno": "TURNO_2", "situacao": "VAGO"},
                {"turno": "TURNO_3", "responsavel_id": resp.id, "situacao": "RESERVA"},
            ],
        )
        cfg = {c.turno: c for c in GrupoEquipeTurno.objects.filter(grupo_id=posto)}
        self.assertEqual(cfg["TURNO_1"].responsavel_id, resp.id)
        self.assertIsNone(cfg["TURNO_2"].responsavel_id)
        self.assertIsNone(cfg["TURNO_3"].responsavel_id)  # reserva não tem titular
        self.assertEqual(cfg["TURNO_3"].situacao, "RESERVA")
        dados = self.client.get(reverse("rh:api_estrutura_equipes_dados")).json()
        g = next(x for x in dados["grupos"] if x["id"] == posto)
        self.assertEqual((g["parent_id"], g["nivel"]), (bloco, 2))
        self.assertEqual(g["setor_id"], self.setor().id)  # posto herda o setor do bloco
        # reeditar removendo turnos
        self.post("api_estrutura_equipes_salvar", {"id": posto, "nome": "PRA 01", "parent_id": bloco, "turnos": [{"turno": "TURNO_1", "situacao": "VAGO"}]})
        self.assertEqual(GrupoEquipeTurno.objects.filter(grupo_id=posto).count(), 1)

    def test_posto_sem_pessoa_exige_vago_ou_reserva(self):
        bloco = self.criar("Corte")
        r = self.post("api_estrutura_equipes_salvar", {"nome": "VFT 01", "parent_id": bloco, "turnos": [{"turno": "TURNO_1", "situacao": "ATIVO"}]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Vago", r.json()["error"])
        # sem informar situação nem pessoa => assume VAGO
        r = self.post("api_estrutura_equipes_salvar", {"nome": "VFT 02", "parent_id": bloco, "turnos": [{"turno": "TURNO_1"}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(GrupoEquipeTurno.objects.get(grupo_id=r.json()["id"]).situacao, "VAGO")

    def test_regras_de_estrutura(self):
        bloco = self.criar("A")
        posto = self.criar("P", bloco)
        # bloco exige setor
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "Sem setor"}).status_code, 400)
        # posto não pode ter posto dentro
        r = self.post("api_estrutura_equipes_salvar", {"nome": "X", "parent_id": posto})
        self.assertEqual(r.status_code, 400)
        # bloco com postos não vira posto
        outro = self.criar("B")
        r = self.post("api_estrutura_equipes_salvar", {"id": bloco, "nome": "A", "parent_id": outro})
        self.assertEqual(r.status_code, 400)
        # nome repetido no mesmo nível
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "a", "setor_id": self.setor().id}).status_code, 400)
        # trocar o setor do bloco propaga aos postos
        novo = self.setor("Laboratório")
        self.post("api_estrutura_equipes_salvar", {"id": bloco, "nome": "A", "setor_id": novo.id})
        self.assertEqual(GrupoEquipe.objects.get(pk=posto).setor_id, novo.id)

    def test_membros_turno_e_mover(self):
        g = self.criar("Corte")
        c1 = _colab("1", "Ana", "TURNO_1")
        c2 = _colab("2", "Bia", "TURNO_2")
        r = self.post("api_estrutura_equipes_membros_atualizar", {"colaborador_ids": [c1.id, c2.id], "grupo_id": g})
        self.assertEqual(r.json()["alterados"], 2)
        url = reverse("rh:api_estrutura_equipes_membros")
        j = self.client.get(url, {"grupo": g, "turno": "TURNO_2"}).json()
        self.assertEqual([m["nome"] for m in j["membros"]], ["Bia"])
        # ajustar turno junto com a movimentação
        self.post("api_estrutura_equipes_membros_atualizar", {"colaborador_ids": [c2.id], "grupo_id": g, "turno": "TURNO_3"})
        c2.refresh_from_db()
        self.assertEqual(c2.turno, "TURNO_3")
        # remover do grupo
        self.post("api_estrutura_equipes_membros_atualizar", {"colaborador_ids": [c1.id], "grupo_id": None})
        self.assertEqual(self.client.get(url, {"grupo": "sem"}).json()["total"], 1)
        # sem grupo_id nem turno é erro
        r = self.post("api_estrutura_equipes_membros_atualizar", {"colaborador_ids": [c1.id]})
        self.assertEqual(r.status_code, 400)

    def test_incluir_subgrupos(self):
        pai = self.criar("Pai")
        filho = self.criar("Filho", pai)
        c = _colab("1", "Ana")
        self.post("api_estrutura_equipes_membros_atualizar", {"colaborador_ids": [c.id], "grupo_id": filho})
        url = reverse("rh:api_estrutura_equipes_membros")
        self.assertEqual(self.client.get(url, {"grupo": pai}).json()["total"], 0)
        self.assertEqual(self.client.get(url, {"grupo": pai, "subgrupos": "1"}).json()["total"], 1)

    def test_excluir_bloco_so_sem_postos_e_solta_membros(self):
        bloco = self.criar("Bloco")
        posto = self.criar("Posto", bloco)
        c = _colab("1", "Ana")
        self.post("api_estrutura_equipes_membros_atualizar", {"colaborador_ids": [c.id], "grupo_id": posto})
        self.assertEqual(self.post("api_estrutura_equipes_excluir", {"id": bloco}).status_code, 400)
        r = self.post("api_estrutura_equipes_excluir", {"id": posto})
        self.assertEqual(r.json()["membros_desvinculados"], 1)
        c.refresh_from_db()
        self.assertIsNone(c.equipe_id)
        self.assertEqual(self.post("api_estrutura_equipes_excluir", {"id": bloco}).status_code, 200)

    def test_usuario_sem_permissao(self):
        u = User.objects.create_user("u", "u@u.com", "x")
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("rh:estrutura_equipes")).status_code, 403)
        self.assertEqual(self.client.get(reverse("rh:api_estrutura_equipes_dados")).status_code, 403)
        self.assertEqual(self.post("api_estrutura_equipes_salvar", {"nome": "X"}).status_code, 403)
