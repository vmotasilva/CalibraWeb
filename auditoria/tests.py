from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .models import ModeloAuditoria, RegistroAuditoria


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
