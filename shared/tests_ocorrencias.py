from django.contrib.auth import get_user_model
from datetime import date

from django.core.cache import cache
from django.test import TestCase, override_settings
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
        self.assertRedirects(resp, reverse("ocorrencias_central") + "?aba=abertas", fetch_redirect_response=False)
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
        self.assertContains(resp, "Plano de ação")
        self.assertContains(resp, "Trocar peça")
        self.assertContains(resp, 'data-acao="redirecionar_acao"')
        resp = self.client.post(reverse("ocorrencias_acao"), {
            "uid": self.uid, "acao": "nova_acao", "texto": "Nova", "responsavel": self.bia.pk, "prazo": "", "next_qs": ""})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(self._item(self.admin).plano), 2)


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
                          {"tipo": "ocorrencia", "causa": "falta de peça", "acao": "comprar", "responsavel": self.ana.pk}])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["o"], 1)
        card = AnaliseItem.objects.get(tipo="ocorrencia")
        acao = AcaoOcorrencia.objects.get(origem="kpi", ocorrencia_id=card.pk)
        self.assertEqual((acao.responsavel_id, acao.descricao), (self.ana.pk, "comprar"))
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

    def test_ocorrencia_exige_responsavel_e_remocao_limpa_plano(self):
        from kpi.models import AnaliseItem
        from shared.models import AcaoOcorrencia

        self.assertEqual(self._salvar([{"tipo": "ocorrencia", "causa": "x"}]).status_code, 400)
        self._salvar([{"tipo": "ocorrencia", "causa": "x", "responsavel": self.ana.pk}])
        card = AnaliseItem.objects.get()
        self._salvar([{"tipo": "comentario", "id": card.pk, "causa": "x"}])  # volta a ser relato
        self.assertFalse(AcaoOcorrencia.objects.exists())
        self._salvar([])
        self.assertFalse(AnaliseItem.objects.exists())
