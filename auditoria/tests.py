from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse

from .models import (
    ComentarioRespostaAuditoria,
    ModeloAuditoria,
    PerguntaAuditoria,
    RegistroAuditoria,
    RelatorioCompartilhadoAuditoria,
)
from .views import _build_registro_report_share_token, registros_por_modelo


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
            exibir_grafico=False,
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
        self.assertFalse(pergunta_duplicada.exibir_grafico)

    def test_modelo_duplicate_uses_custom_target_name(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("auditoria:modelo_duplicate", args=[self.modelo.pk]),
            data={"novo_nome": "MODELO BASE DUPLICACAO - RENOMEADO"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(ModeloAuditoria.objects.filter(nome="MODELO BASE DUPLICACAO - RENOMEADO").exists())

    def test_modelo_duplicate_rejects_existing_name(self):
        self.client.force_login(self.user)
        ModeloAuditoria.objects.create(
            nome="NOME JA EXISTENTE",
            objeto_auditoria="Objeto existente",
            periodicidade="MENSAL",
        )

        response = self.client.post(
            reverse("auditoria:modelo_duplicate", args=[self.modelo.pk]),
            data={"novo_nome": "NOME JA EXISTENTE"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ModeloAuditoria.objects.filter(nome="NOME JA EXISTENTE").count(), 1)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("Já existe um modelo com este nome" in m for m in messages))


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


class PerguntaCreateTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="auditoria_admin_pergunta_create",
            email="auditoria_admin_pergunta_create@example.com",
            password="senha-forte-123",
            is_staff=True,
        )
        try:
            from django_otp.plugins.otp_static.models import StaticDevice

            StaticDevice.objects.create(user=self.user, name="test-device", confirmed=True)
        except Exception:
            pass

        self.modelo = ModeloAuditoria.objects.create(
            nome="MODELO CREATE PERGUNTA",
            objeto_auditoria="Objeto base do teste de criação",
            periodicidade="MENSAL",
        )

    def test_pergunta_create_handles_missing_checkbox_and_saves_false(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("auditoria:pergunta_create"),
            data={
                "modelo": str(self.modelo.pk),
                "subcategoria": "",
                "pergunta": "Pergunta criada via teste",
                "descricao_detalhada": "",
                "tipo_resposta": "SIM_NAO",
                "preenchimento_semanal": "UNICO",
                "opcoes_resposta": "",
                "opcoes_resposta_cores": "",
                "aplicar_no_grid": "on",
                "ordem": "1",
                "obrigatoria": "on",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        pergunta = PerguntaAuditoria.objects.get(modelo=self.modelo, pergunta="Pergunta criada via teste")
        self.assertFalse(pergunta.exibir_grafico)

    def test_pergunta_create_with_iso_preset_applies_official_options(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("auditoria:pergunta_create"),
            data={
                "modelo": str(self.modelo.pk),
                "subcategoria": "",
                "pergunta": "Pergunta com preset ISO",
                "descricao_detalhada": "",
                "conjunto_resposta_padrao": "ISO",
                "tipo_resposta": "SIM_NAO",
                "preenchimento_semanal": "UNICO",
                "opcoes_resposta": "",
                "opcoes_resposta_cores": "",
                "ordem": "1",
                "obrigatoria": "on",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        pergunta = PerguntaAuditoria.objects.get(modelo=self.modelo, pergunta="Pergunta com preset ISO")
        self.assertEqual(pergunta.tipo_resposta, "LISTA")
        self.assertEqual(
            pergunta.opcoes_resposta_list,
            ["Conforme", "Não Conforme", "Não Se Aplica", "Oportunidade de Melhoria"],
        )
        self.assertEqual(
            pergunta.opcoes_resposta_cores,
            {
                "Conforme": "#198754",
                "Não Conforme": "#ff0000",
                "Não Se Aplica": "#d9d9d9",
                "Oportunidade de Melhoria": "#fd7e14",
            },
        )
        self.assertTrue(pergunta.exibir_grafico)
        self.assertTrue(pergunta.aplicar_no_grid)


class PerguntaBulkRespostaPresetTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="auditoria_admin_bulk_resposta",
            email="auditoria_admin_bulk_resposta@example.com",
            password="senha-forte-123",
            is_staff=True,
        )
        try:
            from django_otp.plugins.otp_static.models import StaticDevice

            StaticDevice.objects.create(user=self.user, name="test-device", confirmed=True)
        except Exception:
            pass

        self.modelo = ModeloAuditoria.objects.create(
            nome="MODELO BULK RESPOSTA",
            objeto_auditoria="Objeto do teste em lote",
            periodicidade="MENSAL",
        )
        self.outro_modelo = ModeloAuditoria.objects.create(
            nome="MODELO BULK RESPOSTA EXTERNO",
            objeto_auditoria="Objeto externo ao lote",
            periodicidade="MENSAL",
        )
        self.pergunta_1 = PerguntaAuditoria.objects.create(
            modelo=self.modelo,
            pergunta="Pergunta 1",
            ordem=1,
            tipo_resposta="SIM_NAO",
            exibir_grafico=False,
            aplicar_no_grid=False,
            ativo=True,
        )
        self.pergunta_2 = PerguntaAuditoria.objects.create(
            modelo=self.modelo,
            pergunta="Pergunta 2",
            ordem=2,
            tipo_resposta="NUMERO",
            exibir_grafico=False,
            aplicar_no_grid=False,
            ativo=True,
        )
        self.pergunta_outro_modelo = PerguntaAuditoria.objects.create(
            modelo=self.outro_modelo,
            pergunta="Pergunta externa",
            ordem=1,
            tipo_resposta="DECIMAL",
            exibir_grafico=False,
            aplicar_no_grid=False,
            ativo=True,
        )

    def test_bulk_apply_iso_preset_updates_only_selected_questions_from_model(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("auditoria:perguntas_bulk_apply_resposta"),
            data={
                "modelo": str(self.modelo.pk),
                "filtro_subcategoria": "",
                "conjunto_resposta_padrao": "ISO",
                "pergunta_ids": [
                    str(self.pergunta_1.pk),
                    str(self.pergunta_2.pk),
                    str(self.pergunta_outro_modelo.pk),
                ],
            },
        )

        self.assertEqual(response.status_code, 302)

        self.pergunta_1.refresh_from_db()
        self.pergunta_2.refresh_from_db()
        self.pergunta_outro_modelo.refresh_from_db()

        for pergunta in (self.pergunta_1, self.pergunta_2):
            self.assertEqual(pergunta.tipo_resposta, "LISTA")
            self.assertEqual(
                pergunta.opcoes_resposta_list,
                ["Conforme", "Não Conforme", "Não Se Aplica", "Oportunidade de Melhoria"],
            )
            self.assertEqual(
                pergunta.opcoes_resposta_cores,
                {
                    "Conforme": "#198754",
                    "Não Conforme": "#ff0000",
                    "Não Se Aplica": "#d9d9d9",
                    "Oportunidade de Melhoria": "#fd7e14",
                },
            )
            self.assertTrue(pergunta.exibir_grafico)
            self.assertTrue(pergunta.aplicar_no_grid)

        self.assertEqual(self.pergunta_outro_modelo.tipo_resposta, "DECIMAL")
        self.assertEqual(self.pergunta_outro_modelo.opcoes_resposta, "")
        self.assertEqual(self.pergunta_outro_modelo.opcoes_resposta_cores, {})
        self.assertFalse(self.pergunta_outro_modelo.exibir_grafico)
        self.assertFalse(self.pergunta_outro_modelo.aplicar_no_grid)


class ComentarioPerguntaDeleteTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        user_model = get_user_model()
        self.author = user_model.objects.create_user(
            username="auditoria_comment_author",
            email="auditoria_comment_author@example.com",
            password="senha-forte-123",
            is_staff=True,
        )
        self.other = user_model.objects.create_user(
            username="auditoria_comment_other",
            email="auditoria_comment_other@example.com",
            password="senha-forte-123",
            is_staff=False,
        )

        self.modelo = ModeloAuditoria.objects.create(
            nome="MODELO DELETE COMENTARIO PERGUNTA",
            objeto_auditoria="Objeto de auditoria para delete",
            periodicidade="MENSAL",
        )
        self.pergunta = PerguntaAuditoria.objects.create(
            modelo=self.modelo,
            pergunta="Pergunta para delete de comentário",
            ordem=1,
            tipo_resposta="SIM_NAO",
            ativo=True,
        )
        self.modelo.responsaveis.add(self.other)

        self.comentario = ComentarioRespostaAuditoria.objects.create(
            registro=None,
            pergunta=self.pergunta,
            autor=self.author,
            texto="Comentário removível",
            data_referencia=date.today(),
        )
        self.url = reverse("auditoria:registros_por_modelo", args=[self.modelo.pk])

    def test_author_can_delete_question_comment(self):
        request = self.rf.post(
            self.url,
            data={"action": "delete_question_comment", "comentario_id": str(self.comentario.id)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        request.user = self.author
        response = registros_por_modelo(request, self.modelo.pk)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ComentarioRespostaAuditoria.objects.filter(id=self.comentario.id).exists())

    def test_non_author_cannot_delete_question_comment(self):
        request = self.rf.post(
            self.url,
            data={"action": "delete_question_comment", "comentario_id": str(self.comentario.id)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        request.user = self.other
        response = registros_por_modelo(request, self.modelo.pk)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(ComentarioRespostaAuditoria.objects.filter(id=self.comentario.id).exists())


class RelatorioCompartilhadoSomenteLeituraTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="auditoria_owner_share",
            email="auditoria_owner_share@example.com",
            password="senha-forte-123",
            is_staff=True,
        )
        self.viewer = user_model.objects.create_user(
            username="auditoria_viewer_share",
            email="auditoria_viewer_share@example.com",
            password="senha-forte-123",
            is_staff=False,
        )

        self.modelo = ModeloAuditoria.objects.create(
            nome="MODELO RELATORIO COMPARTILHADO",
            objeto_auditoria="Objeto para teste de compartilhamento",
            periodicidade="MENSAL",
        )
        self.modelo.responsaveis.add(self.owner)

        self.pergunta = PerguntaAuditoria.objects.create(
            modelo=self.modelo,
            pergunta="Pergunta para compartilhamento",
            ordem=1,
            tipo_resposta="SIM_NAO",
            ativo=True,
        )

        self.registro = RegistroAuditoria.objects.create(
            modelo=self.modelo,
            data_auditoria=date(2026, 3, 10),
            periodo_inicio=date(2026, 3, 1),
            periodo_fim=date(2026, 3, 31),
            avaliador=self.owner,
        )

        self.base_url = reverse("auditoria:registros_por_modelo", args=[self.modelo.pk])

    def test_viewer_can_open_shared_link_in_read_only_mode(self):
        self.client.force_login(self.viewer)
        token = _build_registro_report_share_token(
            modelo_id=self.modelo.pk,
            inicio="2026-03-01",
            fim="2026-03-31",
            subcategoria="",
        )

        response = self.client.get(f"{self.base_url}?share_token={token}")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Visualização compartilhada: somente leitura", content)
        self.assertIn("Somente leitura", content)
        self.assertNotIn("Novo Registro", content)
        self.assertNotIn("Novo Comentário", content)

    def test_shared_link_blocks_post_actions(self):
        self.client.force_login(self.viewer)
        token = _build_registro_report_share_token(
            modelo_id=self.modelo.pk,
            inicio="2026-03-01",
            fim="2026-03-31",
            subcategoria="",
        )

        response = self.client.post(
            f"{self.base_url}?share_token={token}",
            data={"action": "add_comment", "comentario": "Tentativa indevida"},
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_shared_link_returns_403(self):
        self.client.force_login(self.viewer)

        response = self.client.get(f"{self.base_url}?share_token=token-invalido")

        self.assertEqual(response.status_code, 403)


class RelatorioCompartilhadoDirecionadoTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.remetente = user_model.objects.create_user(
            username="auditoria_sender",
            email="auditoria_sender@example.com",
            password="senha-forte-123",
            is_staff=True,
        )
        self.destinatario = user_model.objects.create_user(
            username="auditoria_target",
            email="auditoria_target@example.com",
            password="senha-forte-123",
            is_staff=False,
        )
        self.outro = user_model.objects.create_user(
            username="auditoria_other",
            email="auditoria_other@example.com",
            password="senha-forte-123",
            is_staff=False,
        )

        self.modelo = ModeloAuditoria.objects.create(
            nome="MODELO SHARE DIRECIONADO",
            objeto_auditoria="Objeto share direcionado",
            periodicidade="MENSAL",
        )
        self.modelo.responsaveis.add(self.remetente)
        PerguntaAuditoria.objects.create(
            modelo=self.modelo,
            pergunta="Pergunta base",
            ordem=1,
            tipo_resposta="SIM_NAO",
            ativo=True,
        )

        self.url = reverse("auditoria:registros_por_modelo", args=[self.modelo.pk])

    def test_sender_can_create_targeted_share(self):
        self.client.force_login(self.remetente)

        response = self.client.post(
            f"{self.url}?inicio=2026-03-01&fim=2026-03-31",
            data={"action": "share_report_targeted", "destinatario_id": str(self.destinatario.id)},
        )

        self.assertEqual(response.status_code, 302)
        share = RelatorioCompartilhadoAuditoria.objects.get(modelo=self.modelo, remetente=self.remetente)
        self.assertEqual(share.destinatario_id, self.destinatario.id)
        self.assertEqual(share.inicio.isoformat(), "2026-03-01")
        self.assertEqual(share.fim.isoformat(), "2026-03-31")

    def test_only_target_user_can_open_targeted_share(self):
        share = RelatorioCompartilhadoAuditoria.objects.create(
            modelo=self.modelo,
            remetente=self.remetente,
            destinatario=self.destinatario,
        )

        self.client.force_login(self.outro)
        response = self.client.get(f"{self.url}?share_token={share.token}")
        self.assertEqual(response.status_code, 403)

    def test_target_open_registers_receipt_proof(self):
        share = RelatorioCompartilhadoAuditoria.objects.create(
            modelo=self.modelo,
            remetente=self.remetente,
            destinatario=self.destinatario,
        )

        self.client.force_login(self.destinatario)
        response = self.client.get(f"{self.url}?share_token={share.token}")

        self.assertEqual(response.status_code, 200)
        share.refresh_from_db()
        self.assertIsNotNone(share.recebido_em)
        self.assertIsNotNone(share.primeiro_acesso_em)

    def test_home_shows_received_share_notification(self):
        RelatorioCompartilhadoAuditoria.objects.create(
            modelo=self.modelo,
            remetente=self.remetente,
            destinatario=self.destinatario,
        )

        self.client.force_login(self.destinatario)
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Relatórios Compartilhados Comigo", content)
