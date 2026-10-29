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
