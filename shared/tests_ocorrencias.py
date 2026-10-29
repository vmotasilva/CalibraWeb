from django.contrib.auth import get_user_model
from datetime import date

from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from laboratorio.models import OcorrenciaLaboratorio
from qms.models import OcorrenciaInstrumento
from shared import ocorrencias as central


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CentralOcorrenciasTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.admin = U.objects.create_user("admin", password="x", is_superuser=True, is_staff=True)
        self.outro = U.objects.create_user("outro", password="x", is_superuser=True, is_staff=True)
        self.lab_minha = OcorrenciaLaboratorio.objects.create(assunto="Minha", detalhamento="d", criado_por=self.admin)
        self.lab_outra = OcorrenciaLaboratorio.objects.create(assunto="Outra", detalhamento="d", criado_por=self.outro)
        self.met = OcorrenciaInstrumento.objects.create(
            tipo="AVARIA", descricao="quebrou", usuario_responsavel=self.admin
        )

    def test_envolvidas_vem_primeiro_e_contagem(self):
        itens = central.listar_ocorrencias(self.admin, "abertas")
        self.assertEqual(len(itens), 3)
        self.assertTrue(all(i.envolve_usuario for i in itens[:2]))
        self.assertFalse(itens[-1].envolve_usuario)
        self.assertEqual(itens[-1].titulo, "Outra")
        self.assertEqual(central.contar_ocorrencias(self.admin), {"minhas": 2, "abertas": 3})

    def test_anotar_e_encerrar_laboratorio(self):
        r = central.executar_acao(self.admin, f"laboratorio:{self.lab_minha.pk}", "anotar", {"texto": "andamento"})
        self.assertTrue(r.ok)
        self.assertEqual(self.lab_minha.anotacoes_registradas.count(), 1)
        r = central.executar_acao(self.admin, f"laboratorio:{self.lab_minha.pk}", "encerrar", {"texto": "ok"})
        self.assertTrue(r.ok)
        self.lab_minha.refresh_from_db()
        self.assertIsNotNone(self.lab_minha.data_encerramento)
        self.assertEqual(self.lab_minha.observacoes_encerramento, "ok")
        self.assertEqual(central.contar_ocorrencias(self.admin)["abertas"], 2)

    def test_metrologia_mensagem_atribuir_encerrar_reabrir(self):
        uid = f"metrologia:{self.met.pk}"
        self.assertFalse(central.executar_acao(self.admin, uid, "mensagem", {"texto": ""}).ok)
        r = central.executar_acao(self.admin, uid, "mensagem", {"texto": "ver", "destinatarios": [str(self.outro.pk)]})
        self.assertTrue(r.ok)
        self.assertEqual(self.met.mensagens.count(), 1)
        self.assertTrue(central.executar_acao(self.admin, uid, "atribuir", {"responsavel": str(self.outro.pk)}).ok)
        self.assertTrue(central.executar_acao(self.admin, uid, "encerrar", {}).ok)
        self.met.refresh_from_db()
        self.assertEqual((self.met.status, self.met.usuario_responsavel_id), ("ENCERRADA", self.outro.pk))
        self.assertEqual(len(central.listar_ocorrencias(self.admin, "encerradas")), 1)
        self.assertTrue(central.executar_acao(self.admin, uid, "reabrir", {}).ok)

    def test_usuario_sem_acesso_nao_ve_nem_age(self):
        sem = get_user_model().objects.create_user("sem", password="x")
        self.assertEqual(central.listar_ocorrencias(sem, "abertas"), [])
        r = central.executar_acao(sem, f"laboratorio:{self.lab_minha.pk}", "anotar", {"texto": "x"})
        self.assertFalse(r.ok)

    def test_uid_invalido(self):
        self.assertFalse(central.executar_acao(self.admin, "foo:1", "x", {}).ok)
        self.assertFalse(central.executar_acao(self.admin, "laboratorio:abc", "x", {}).ok)

    def test_telas(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("ocorrencias_central"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Minha")
        self.assertContains(resp, "Central de Ocorrências")
        resp = self.client.post(
            reverse("ocorrencias_acao"),
            {"uid": f"laboratorio:{self.lab_minha.pk}", "acao": "anotar", "texto": "via tela", "next_qs": "aba=abertas&x=1"},
        )
        uid = f"laboratorio:{self.lab_minha.pk}"
        self.assertRedirects(
            resp, reverse("ocorrencias_central") + f"?aba=abertas&abrir=laboratorio%3A{self.lab_minha.pk}",
            fetch_redirect_response=False)
        self.assertEqual(self.lab_minha.anotacoes_registradas.count(), 1)
        # o ícone aparece no menu das demais telas
        self.assertContains(self.client.get(reverse("inbox")), reverse("ocorrencias_central"))

    def test_pcp_e_auditoria(self):
        from auditoria.models import ComentarioRespostaAuditoria, ModeloAuditoria, PerguntaAuditoria
        from pcp.models import Formulario, FormularioVersao, Ocorrencia, Pagina, Turno, Verificacao

        from organization.models import Setor

        form = Formulario.objects.create(setor=Setor.objects.create(nome="S"), codigo="FOR.1", titulo="F")
        versao = FormularioVersao.objects.create(formulario=form, revisao="R1")
        pag = Pagina.objects.create(versao=versao, nome="Pagina X")
        ver = Verificacao.objects.create(pagina=pag, data=date(2026, 10, 22), turno=Turno.objects.create(nome="T1", sigla="T1"))
        oc_pcp = Ocorrencia.objects.create(verificacao=ver, tipo="tratativa", descricao="vacuo", criado_por=self.admin)

        modelo = ModeloAuditoria.objects.create(nome="MOD", objeto_auditoria="o", periodicidade="MENSAL")
        pergunta = PerguntaAuditoria.objects.create(modelo=modelo, pergunta="Perg", ordem=1, tipo_resposta="SIM_NAO")
        oc_aud = ComentarioRespostaAuditoria.objects.create(
            pergunta=pergunta, autor=self.admin, texto="falha", requer_tratativa=True, data_referencia=date.today()
        )

        itens = {i.origem: i for i in central.listar_ocorrencias(self.admin, "abertas")}
        self.assertTrue(itens["pcp"].envolve_usuario and itens["auditoria"].envolve_usuario)

        self.assertFalse(central.executar_acao(self.admin, f"pcp:{oc_pcp.pk}", "tratar", {"texto": ""}).ok)
        self.assertTrue(central.executar_acao(self.admin, f"pcp:{oc_pcp.pk}", "tratar", {"texto": "feito"}).ok)
        oc_pcp.refresh_from_db()
        self.assertEqual((oc_pcp.status, oc_pcp.tratada_por_id), ("tratada", self.admin.pk))

        self.assertTrue(central.executar_acao(self.admin, f"auditoria:{oc_aud.pk}", "resolver", {"texto": "corrigido"}).ok)
        oc_aud.refresh_from_db()
        self.assertEqual((oc_aud.status, oc_aud.resolucao), ("RESOLVIDA", "corrigido"))
        self.assertTrue(central.executar_acao(self.admin, f"auditoria:{oc_aud.pk}", "reabrir", {}).ok)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("ocorrencias_central") + "?aba=encerradas").status_code, 200)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PlanoDeAcaoTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.admin = U.objects.create_user("admin", password="x", is_superuser=True, is_staff=True)
        self.ana = U.objects.create_user("ana", password="x", is_superuser=True, is_staff=True)
        self.bia = U.objects.create_user("bia", password="x", is_superuser=True, is_staff=True)
        self.oc = OcorrenciaLaboratorio.objects.create(assunto="Falha", detalhamento="d", criado_por=self.admin)
        self.uid = f"laboratorio:{self.oc.pk}"

    def _acao(self, user, acao, **dados):
        return central.executar_acao(user, self.uid, acao, dados)

    def _item(self, user):
        return next(i for i in central.listar_ocorrencias(user, "abertas") if i.uid == self.uid)

    def test_varias_acoes_com_responsavel_e_prazo(self):
        hoje = date.today().isoformat()
        self.assertFalse(self._acao(self.admin, "nova_acao", texto="x", responsavel="").ok)  # responsável obrigatório
        self.assertFalse(self._acao(self.admin, "nova_acao", texto="x", responsavel=str(self.ana.pk), prazo="2001-01-01").ok)
        self.assertTrue(self._acao(self.admin, "nova_acao", texto="Trocar peça", responsavel=str(self.ana.pk), prazo=hoje).ok)
        self.assertTrue(self._acao(self.admin, "nova_acao", texto="Validar", responsavel=str(self.bia.pk)).ok)
        item = self._item(self.ana)
        self.assertEqual(len(item.plano), 2)
        self.assertEqual(item.responsaveis, ["ana", "bia"])
        self.assertTrue(item.envolve_usuario and item.papel == "Responsável pela ação")
        self.assertEqual(central.contar_ocorrencias(self.bia)["minhas"], 1)

    def test_redirecionar_mantem_historico(self):
        self._acao(self.admin, "nova_acao", texto="Trocar peça", responsavel=str(self.ana.pk))
        a1 = self._item(self.admin).plano[0]
        self.assertFalse(self._acao(self.ana, "redirecionar_acao", acao_id=a1.id, responsavel=str(self.bia.pk), texto="").ok)
        self.assertFalse(self._acao(self.ana, "redirecionar_acao", acao_id=a1.id, responsavel=str(self.ana.pk), texto="m").ok)
        self.assertTrue(self._acao(self.ana, "redirecionar_acao", acao_id=a1.id, responsavel=str(self.bia.pk), texto="Férias").ok)
        plano = self._item(self.admin).plano
        self.assertEqual([p.status for p in plano], ["REDIRECIONADA", "ABERTA"])
        self.assertEqual((plano[0].para, plano[1].de, plano[0].resultado), ("bia", "ana", "Férias"))
        self.assertEqual(plano[1].responsavel, "bia")
        self.assertEqual(central.contar_ocorrencias(self.ana)["minhas"], 0)
        self.assertEqual(central.contar_ocorrencias(self.bia)["minhas"], 1)

    def test_concluir_cancelar_e_bloqueio_de_encerramento(self):
        from django.contrib.auth.models import User

        comum = User.objects.create_user("comum", password="x")
        self._acao(self.admin, "nova_acao", texto="A", responsavel=str(self.ana.pk))
        aid = self._item(self.admin).plano[0].id
        r = self._acao(self.admin, "encerrar", texto="ok")
        self.assertFalse(r.ok)
        self.assertIn("ações em aberto", r.msg)
        self.assertFalse(self._acao(comum, "concluir_acao", acao_id=aid).ok)  # sem acesso à ocorrência
        self.assertTrue(self._acao(self.ana, "concluir_acao", acao_id=aid, texto="feito").ok)
        self.assertFalse(self._acao(self.ana, "concluir_acao", acao_id=aid).ok)  # já encerrada
        self._acao(self.admin, "nova_acao", texto="B", responsavel=str(self.bia.pk))
        bid = [p for p in self._item(self.admin).plano if p.status == "ABERTA"][0].id
        self.assertTrue(self._acao(self.admin, "cancelar_acao", acao_id=bid, texto="desnecessária").ok)
        self.assertTrue(self._acao(self.admin, "encerrar", texto="ok").ok)
        # em ocorrência encerrada não há mais ação nova
        self.assertFalse(self._acao(self.admin, "nova_acao", texto="C", responsavel=str(self.ana.pk)).ok)

    def test_acao_aparece_na_caixa_de_entrada(self):
        from shared.inbox import get_user_inbox_items

        self._acao(self.admin, "nova_acao", texto="Trocar peça", responsavel=str(self.ana.pk))
        itens = [i for i in get_user_inbox_items(self.ana) if i.module == "Ocorrências"]
        self.assertEqual(len(itens), 1)
        self.assertIn("Trocar peça", itens[0].description)

    def test_tela_exibe_plano_e_acoes(self):
        self._acao(self.admin, "nova_acao", texto="Trocar peça", responsavel=str(self.ana.pk))
        self.client.force_login(self.ana)
        resp = self.client.get(reverse("ocorrencias_central"))
        self.assertContains(resp, "data-plano-mount")          # o pop-up monta o widget do plano
        self.assertContains(resp, "shared/plano_acao.js")
        self.assertContains(resp, "1 ação(ões)")                  # resumo no card


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class OcorrenciaKpiTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.admin = U.objects.create_user("admin", password="x", is_superuser=True, is_staff=True)
        self.ana = U.objects.create_user("ana", password="x", is_superuser=True, is_staff=True)
        from kpi.models import Indicador

        self.ind = Indicador.objects.create(nome="Late Orders", meta=1, sentido="menor", periodicidade="mensal")
        self.client.force_login(self.admin)

    def _salvar(self, itens):
        import json

        return self.client.post(reverse("kpi:analise_salvar", args=[self.ind.pk]),
                                {"gran": "mensal", "data": "2026-10-01", "setor": "", "itens": json.dumps(itens)})

    def test_card_ocorrencia_cria_acao_e_entra_na_central_sem_perder_estado(self):
        from kpi.models import AnaliseItem
        from shared.models import AcaoOcorrencia

        r = self._salvar([{"tipo": "comentario", "causa": "só um relato"},
                          {"tipo": "ocorrencia", "causa": "falta de peça", "acao": "comprar", "responsaveis": [self.ana.pk, self.admin.pk]}])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["o"], 1)
        card = AnaliseItem.objects.get(tipo="ocorrencia")
        acao = AcaoOcorrencia.objects.get(origem="kpi", ocorrencia_id=card.pk)
        self.assertEqual(acao.descricao, "comprar")
        self.assertEqual(set(acao.responsaveis.values_list("pk", flat=True)), {self.ana.pk, self.admin.pk})
        itens = central.listar_ocorrencias(self.ana, "abertas", "kpi")
        self.assertEqual(len(itens), 1)  # o relato não vira ocorrência
        self.assertTrue(itens[0].envolve_usuario)
        self.assertIn("Late Orders", itens[0].titulo)

        # resolver na central (após concluir a ação) e re-salvar o card no painel não perde a resolução
        self.assertFalse(central.executar_acao(self.admin, itens[0].uid, "resolver", {"texto": "ok"}).ok)
        a = itens[0].plano[0]
        self.assertTrue(central.executar_acao(self.ana, itens[0].uid, "concluir_acao", {"acao_id": a.id}).ok)
        self.assertTrue(central.executar_acao(self.admin, itens[0].uid, "resolver", {"texto": "ok"}).ok)
        r = self._salvar([{"tipo": "ocorrencia", "id": card.pk, "causa": "falta de peça (editado)", "acao": "comprar"}])
        self.assertEqual(r.status_code, 200, r.content)
        card.refresh_from_db()
        self.assertEqual((card.status, card.resolucao, card.causa), ("RESOLVIDA", "ok", "falta de peça (editado)"))
        self.assertEqual(AcaoOcorrencia.objects.filter(origem="kpi", ocorrencia_id=card.pk).count(), 1)

    def test_relato_vira_ocorrencia_sem_acao_e_remocao_limpa_plano(self):
        from kpi.models import AnaliseItem
        from shared.models import AcaoOcorrencia

        # relato primeiro; a conversão em ocorrência não exige ação: ela é atribuída depois, no pop-up
        self._salvar([{"tipo": "comentario", "causa": "x"}])
        card = AnaliseItem.objects.get()
        self._salvar([{"tipo": "ocorrencia", "id": card.pk, "causa": "x"}])
        card.refresh_from_db()
        self.assertEqual(card.tipo, AnaliseItem.TIPO_OCORRENCIA)
        self.assertFalse(AcaoOcorrencia.objects.exists())
        self._salvar([{"tipo": "ocorrencia", "id": card.pk, "causa": "x", "responsaveis": [self.ana.pk]}])
        self.assertEqual(AcaoOcorrencia.objects.count(), 1)
        self._salvar([{"tipo": "comentario", "id": card.pk, "causa": "x"}])  # volta a ser relato
        self.assertFalse(AcaoOcorrencia.objects.exists())
        self._salvar([])
        self.assertFalse(AnaliseItem.objects.exists())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PopupEFiltroAtrasoTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.admin = U.objects.create_user("admin", password="x", is_superuser=True, is_staff=True)
        self.em_dia = OcorrenciaLaboratorio.objects.create(assunto="Em dia", detalhamento="d", criado_por=self.admin)
        self.atrasada = OcorrenciaLaboratorio.objects.create(assunto="Atrasada", detalhamento="d", criado_por=self.admin)
        self.client.force_login(self.admin)

    def _atrasar(self):
        from shared.models import AcaoOcorrencia

        a = AcaoOcorrencia.objects.create(
            origem="laboratorio", ocorrencia_id=self.atrasada.pk, descricao="X",
            prazo=date(2020, 1, 1), criado_por=self.admin)
        a.responsaveis.add(self.admin)

    def test_filtro_em_atraso(self):
        self._atrasar()
        url = reverse("ocorrencias_central")
        resp = self.client.get(url + "?aba=abertas")
        self.assertEqual(resp.context["total_vencidas"], 1)
        self.assertEqual(len(resp.context["itens"]), 2)
        resp = self.client.get(url + "?aba=abertas&atraso=1")
        self.assertEqual([i.titulo for i in resp.context["itens"]], ["Atrasada"])
        self.assertTrue(resp.context["atraso"])
        # o filtro não se aplica às encerradas
        self.assertFalse(self.client.get(url + "?aba=encerradas&atraso=1").context["atraso"])

    def test_popup_com_detalhe_e_abertura_automatica(self):
        self._atrasar()
        uid = f"laboratorio:{self.atrasada.pk}"
        resp = self.client.get(reverse("ocorrencias_central") + "?aba=abertas&abrir=" + uid)
        self.assertContains(resp, f'data-oc-abrir="{uid}"')       # card clicável
        self.assertContains(resp, f'<template data-oc-detalhe="{uid}"')  # conteúdo do pop-up
        self.assertContains(resp, 'id="ocDetalheModal"')
        self.assertContains(resp, "abrirDetalhe('laboratorio:%d')" % self.atrasada.pk)
        # uid desconhecido ou fora da lista não abre nada
        self.assertEqual(self.client.get(reverse("ocorrencias_central") + "?abrir=foo:1").context["abrir"], "")

    def test_acao_preserva_filtros_e_reabre_popup(self):
        resp = self.client.post(reverse("ocorrencias_acao"), {
            "uid": f"laboratorio:{self.em_dia.pk}", "acao": "anotar", "texto": "ok",
            "next_qs": "aba=abertas&origem=laboratorio&atraso=1&abrir=lixo&x=1"})
        self.assertEqual(
            resp["Location"],
            reverse("ocorrencias_central") + f"?aba=abertas&origem=laboratorio&atraso=1&abrir=laboratorio%3A{self.em_dia.pk}")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class VariosResponsaveisEApiTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.admin = U.objects.create_user("admin", password="x", is_superuser=True, is_staff=True)
        self.ana = U.objects.create_user("ana", first_name="Ana", last_name="Souza", password="x", is_superuser=True, is_staff=True)
        self.bia = U.objects.create_user("bia", first_name="Bia", password="x", is_superuser=True, is_staff=True)
        self.inativo = U.objects.create_user("zeca", first_name="Zeca", password="x", is_active=False)
        self.oc = OcorrenciaLaboratorio.objects.create(assunto="Falha", detalhamento="d", criado_por=self.admin)
        self.uid = f"laboratorio:{self.oc.pk}"
        self.client.force_login(self.admin)

    def _post(self, acao, **dados):
        return self.client.post(reverse("ocorrencias_api_plano_acao"), {"uid": self.uid, "acao": acao, **dados})

    def test_busca_ajax_nos_colaboradores(self):
        from rh.models import Colaborador

        Colaborador.objects.create(matricula="1", nome_completo="Ana Souza", user_django=self.ana)
        Colaborador.objects.create(matricula="2", nome_completo="Beatriz Camargo Lima", user_django=self.bia)
        Colaborador.objects.create(matricula="3", nome_completo="Zeca Inativo", user_django=self.inativo)
        Colaborador.objects.create(matricula="4", nome_completo="Sem Usuario")           # sem login: não pode agir
        Colaborador.objects.create(matricula="5", nome_completo="Ana Desligada", is_active=False)
        url = reverse("ocorrencias_api_usuarios")
        res = self.client.get(url, {"q": "camargo"}).json()["results"]
        self.assertEqual([(r["id"], r["nome"]) for r in res], [(self.bia.pk, "Beatriz Camargo Lima")])
        self.assertEqual([r["nome"] for r in self.client.get(url, {"q": "ana"}).json()["results"]], ["Ana Souza"])
        self.assertEqual(len(self.client.get(url, {"q": "a s"}).json()["results"]), 1)   # todos os termos
        self.assertEqual([r["id"] for r in self.client.get(url, {"q": "2"}).json()["results"]], [self.bia.pk])  # matrícula
        self.assertEqual(len(self.client.get(url).json()["results"]), 2)                 # inativos/sem usuário fora
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)  # exige login

    def test_acao_com_varios_responsaveis_pela_api(self):
        r = self._post("nova_acao", texto="Trocar peça", responsaveis=[self.ana.pk, self.bia.pk], prazo="")
        self.assertEqual(r.status_code, 200, r.content)
        acao = r.json()["plano"]["acoes"][0]
        self.assertEqual([x["nome"] for x in acao["responsaveis"]], ["Ana Souza", "Bia"])
        for u in (self.ana, self.bia):
            self.assertEqual(central.contar_ocorrencias(u)["minhas"], 1)
        # qualquer um dos responsáveis conclui
        r = self.client.post(reverse("ocorrencias_api_plano_acao"), {"uid": self.uid, "acao": "concluir_acao", "acao_id": acao["id"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["plano"]["acoes"][0]["status"], "CONCLUIDA")

    def test_responsavel_obrigatorio_e_redirecionar_para_novo_grupo(self):
        self.assertEqual(self._post("nova_acao", texto="x").status_code, 400)
        self.assertEqual(self._post("nova_acao", texto="x", responsaveis=[self.inativo.pk]).status_code, 400)
        self._post("nova_acao", texto="x", responsaveis=[self.ana.pk, self.bia.pk])
        aid = central.plano_json(self.admin, "laboratorio", self.oc.pk)["acoes"][0]["id"]
        # mesmo grupo: recusado; grupo diferente: redireciona e preserva o histórico
        r = self._post("redirecionar_acao", acao_id=aid, texto="m", responsaveis=[self.bia.pk, self.ana.pk])
        self.assertEqual(r.status_code, 400)
        r = self._post("redirecionar_acao", acao_id=aid, texto="Férias", responsaveis=[self.admin.pk, self.bia.pk])
        self.assertEqual(r.status_code, 200, r.content)
        acoes = r.json()["plano"]["acoes"]
        self.assertEqual([a["status"] for a in acoes], ["REDIRECIONADA", "ABERTA"])
        self.assertEqual(acoes[0]["para"], "admin, Bia")
        self.assertEqual(acoes[1]["de"], "Ana Souza, Bia")

    def test_api_do_plano_respeita_acesso_e_ocorrencia_encerrada(self):
        from django.contrib.auth.models import User

        url = reverse("ocorrencias_api_plano", args=["laboratorio", self.oc.pk])
        self.assertTrue(self.client.get(url).json()["pode_criar"])
        self.assertEqual(self.client.get(reverse("ocorrencias_api_plano", args=["laboratorio", 99999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("ocorrencias_api_plano", args=["xyz", 1])).status_code, 404)
        self.assertEqual(self._post("encerrar", texto="x").status_code, 400)  # só ações do plano pela API
        central.executar_acao(self.admin, self.uid, "encerrar", {"texto": "ok"})
        self.assertFalse(self.client.get(url).json()["pode_criar"])
        self.client.force_login(User.objects.create_user("comum", password="x"))
        self.assertEqual(self.client.get(url).status_code, 404)  # sem acesso à origem


class MigracaoResponsaveisTests(TransactionTestCase):
    """0002: o responsável único anterior vira o primeiro da lista de responsáveis da ação."""

    def test_copia_responsavel_antigo(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        U = get_user_model()
        executor = MigrationExecutor(connection)
        if ("shared", "0001_initial") not in executor.loader.graph.nodes:
            self.skipTest("migrações desativadas nesta configuração de teste (rode com config.settings)")
        antes, depois = [("shared", "0001_initial")], [("shared", "0002_acaoocorrencia_responsaveis")]
        executor.migrate(antes)
        try:
            AcaoAntiga = executor.loader.project_state(antes).apps.get_model("shared", "AcaoOcorrencia")
            u = U.objects.create_user("ana", password="x")
            AcaoAntiga.objects.create(origem="laboratorio", ocorrencia_id=1, descricao="d", responsavel_id=u.pk)
            AcaoAntiga.objects.create(origem="laboratorio", ocorrencia_id=2, descricao="sem responsável")
            executor = MigrationExecutor(connection)
            executor.migrate(depois)
            Acao = executor.loader.project_state(depois).apps.get_model("shared", "AcaoOcorrencia")
            self.assertEqual(list(Acao.objects.get(ocorrencia_id=1).responsaveis.values_list("pk", flat=True)), [u.pk])
            self.assertEqual(Acao.objects.get(ocorrencia_id=2).responsaveis.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ComentariosDaAcaoTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.admin = U.objects.create_user("admin", password="x", is_superuser=True, is_staff=True)
        self.ana = U.objects.create_user("ana", first_name="Ana", password="x", is_superuser=True, is_staff=True)
        self.oc = OcorrenciaLaboratorio.objects.create(assunto="Falha", detalhamento="d", criado_por=self.admin)
        self.uid = f"laboratorio:{self.oc.pk}"
        self.client.force_login(self.admin)
        self.client.post(reverse("ocorrencias_api_plano_acao"), {
            "uid": self.uid, "acao": "nova_acao", "texto": "Trocar peça", "responsaveis": [self.ana.pk]})
        self.aid = central.plano_json(self.admin, "laboratorio", self.oc.pk)["acoes"][0]["id"]

    def _comentar(self, texto):
        return self.client.post(reverse("ocorrencias_api_plano_acao"), {
            "uid": self.uid, "acao": "comentar_acao", "acao_id": self.aid, "texto": texto})

    def test_varios_comentarios_na_acao(self):
        self.assertEqual(self._comentar("Qual peça exatamente?").status_code, 200)
        self.client.force_login(self.ana)
        r = self._comentar("A do lote 7.")
        self.assertEqual(r.status_code, 200, r.content)
        coments = r.json()["plano"]["acoes"][0]["comentarios"]
        self.assertEqual([c["texto"] for c in coments], ["Qual peça exatamente?", "A do lote 7."])
        self.assertEqual(coments[1]["autor"], "Ana")

    def test_comentario_vazio_recusado_e_vale_em_acao_encerrada(self):
        self.assertEqual(self._comentar("  ").status_code, 400)
        self.client.post(reverse("ocorrencias_api_plano_acao"), {"uid": self.uid, "acao": "concluir_acao", "acao_id": self.aid})
        self.assertEqual(self._comentar("Obrigado").status_code, 200)
