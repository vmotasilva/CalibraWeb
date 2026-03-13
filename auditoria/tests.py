from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .models import ComentarioRespostaAuditoria, ModeloAuditoria, PerguntaAuditoria, RegistroAuditoria


class ModeloDeleteProtectedTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="auditoria_admin",
            email="auditoria_admin@example.com",
            password="senha-forte-123",
            is_staff=True,
        )
        try:
            from django_otp.plugins.otp_static.models import StaticDevice

            StaticDevice.objects.create(user=self.user, name="test-device", confirmed=True)
        except Exception:
            # Alguns ambientes de teste removem apps OTP; nesse caso seguimos sem dispositivo.
            pass

        self.modelo = ModeloAuditoria.objects.create(
            nome="MODELO TESTE PROTECT",
            objeto_auditoria="Objeto de auditoria para teste",
            periodicidade="MENSAL",
        )

        RegistroAuditoria.objects.create(
            modelo=self.modelo,
            data_auditoria=date.today(),
            periodo_inicio=date.today(),
            periodo_fim=date.today(),
        )

    def test_delete_modelo_with_registros_protegidos_returns_redirect_and_message(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("auditoria:modelo_delete", args=[self.modelo.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("auditoria:modelos_list"))
        self.assertTrue(ModeloAuditoria.objects.filter(pk=self.modelo.pk).exists())

        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("Não foi possível remover este modelo" in m for m in messages),
            f"Mensagem esperada não encontrada. Mensagens: {messages}",
        )


class ModeloDuplicateTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="auditoria_admin_duplicate",
            email="auditoria_admin_duplicate@example.com",
            password="senha-forte-123",
            is_staff=True,
        )
        try:
            from django_otp.plugins.otp_static.models import StaticDevice

            StaticDevice.objects.create(user=self.user, name="test-device", confirmed=True)
        except Exception:
            pass

        self.modelo = ModeloAuditoria.objects.create(
            nome="MODELO BASE DUPLICACAO",
            objeto_auditoria="Objeto base",
            periodicidade="MENSAL",
        )
        self.pergunta = PerguntaAuditoria.objects.create(
            modelo=self.modelo,
            pergunta="Pergunta com descrição",
            descricao_detalhada="Descrição detalhada importante para instrução.",
            tipo_resposta="SIM_NAO",
            ordem=1,
            obrigatoria=True,
            ativo=True,
        )

    def test_modelo_duplicate_copies_pergunta_descricao_detalhada(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("auditoria:modelo_duplicate", args=[self.modelo.pk]))

        self.assertEqual(response.status_code, 302)
        novo_modelo = ModeloAuditoria.objects.exclude(pk=self.modelo.pk).get()
        pergunta_duplicada = PerguntaAuditoria.objects.get(modelo=novo_modelo, ordem=1)
        self.assertEqual(
            pergunta_duplicada.descricao_detalhada,
            "Descrição detalhada importante para instrução.",
        )


class ComentarioPerguntaSemRegistroTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="auditoria_user",
            email="auditoria_user@example.com",
            password="senha-forte-123",
            is_staff=True,
        )
        try:
            from django_otp.plugins.otp_static.models import StaticDevice

            StaticDevice.objects.create(user=self.user, name="test-device", confirmed=True)
        except Exception:
            pass

        self.modelo = ModeloAuditoria.objects.create(
            nome="MODELO COMENTARIO DATA",
            objeto_auditoria="Objeto de auditoria para comentário por data",
            periodicidade="MENSAL",
        )
        self.pergunta = PerguntaAuditoria.objects.create(
            modelo=self.modelo,
            pergunta="Pergunta de teste",
            ordem=1,
            tipo_resposta="SIM_NAO",
            ativo=True,
        )

    def test_add_question_comment_without_registro_persists_with_data_referencia(self):
        self.client.force_login(self.user)
        data_alvo = date(2026, 3, 10)

        response = self.client.post(
            reverse("auditoria:registros_por_modelo", args=[self.modelo.pk]),
            data={
                "action": "add_question_comment",
                "pergunta_id": str(self.pergunta.pk),
                "comentario_data": data_alvo.isoformat(),
                "comentario": "Comentário sem registro na data",
            },
        )

        self.assertEqual(response.status_code, 302)
        comentario = ComentarioRespostaAuditoria.objects.get(pergunta=self.pergunta)
        self.assertIsNone(comentario.registro)
        self.assertEqual(comentario.data_referencia, data_alvo)
        self.assertEqual(comentario.texto, "Comentário sem registro na data")

    def test_registro_create_preloads_comments_from_matching_period(self):
        self.client.force_login(self.user)
        data_alvo = date.today()
        ComentarioRespostaAuditoria.objects.create(
            registro=None,
            pergunta=self.pergunta,
            autor=self.user,
            texto="Comentário pré-registro para exibir no formulário",
            data_referencia=data_alvo,
        )

        response = self.client.get(reverse("auditoria:registro_create_modelo", args=[self.modelo.pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("comentarios-dados", content)
        self.assertIn("Coment\\u00e1rio pr\\u00e9-registro para exibir no formul\\u00e1rio", content)
