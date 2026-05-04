from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from maquinas.models import CategoriaMaquina

from .models import CategoriaInsumo, ModeloAuditoria, PerguntaAuditoria, RegistroAuditoria


class InsumosModuleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="insumos.admin",
            password="senha-forte-123",
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_modulo_exibe_visao_de_controle_de_insumos(self):
        response = self.client.get(reverse("insumos:modulo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Controle de Insumos")
        self.assertContains(response, "Categorias ativas")
        self.assertContains(response, reverse("insumos:categorias_list"))
        self.assertContains(response, reverse("insumos:selecionar_modelo_preenchimento"))

    def test_categoria_pode_ser_criada_e_listada(self):
        response = self.client.post(
            reverse("insumos:categoria_create"),
            {
                "nome": "Lubrificantes",
                "descricao": "Itens voltados a lubrificação e proteção.",
                "ativo": "on",
            },
        )

        self.assertRedirects(response, reverse("insumos:categorias_list"))
        self.assertTrue(CategoriaInsumo.objects.filter(nome="Lubrificantes").exists())

        list_response = self.client.get(reverse("insumos:categorias_list"))
        self.assertContains(list_response, "Lubrificantes")

    def test_formulario_de_cadastro_exibe_categoria_e_tipo_maquina(self):
        categoria = CategoriaInsumo.objects.create(nome="Consumíveis")
        categoria_maquina = CategoriaMaquina.objects.create(nome="Misturadores")

        response = self.client.get(reverse("insumos:modelo_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novo Cadastro de Insumo")
        self.assertContains(response, 'id="id_categoria"', html=False)
        self.assertContains(response, 'id="id_tipo_maquina"', html=False)
        self.assertContains(response, categoria.nome)
        self.assertContains(response, categoria_maquina.nome)

    def test_listagem_de_cadastros_exibe_categoria_tipo_maquina_e_contadores(self):
        categoria = CategoriaInsumo.objects.create(nome="Lubrificantes")
        categoria_maquina = CategoriaMaquina.objects.create(nome="Linha de moagem")
        modelo = ModeloAuditoria.objects.create(
            nome="Controle de óleo hidráulico",
            categoria=categoria,
            tipo_maquina=categoria_maquina,
            objeto_auditoria="Monitoramento do óleo utilizado na prensa hidráulica.",
            periodicidade="MENSAL",
            dia_mes=10,
            ativo=True,
        )
        PerguntaAuditoria.objects.create(
            modelo=modelo,
            pergunta="Nível dentro do padrão?",
            tipo_resposta="SIM_NAO",
            ordem=1,
        )
        RegistroAuditoria.objects.create(
            modelo=modelo,
            data_auditoria="2026-05-01",
            periodo_inicio="2026-05-01",
            periodo_fim="2026-05-01",
            avaliador=self.user,
        )

        response = self.client.get(reverse("insumos:modelos_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cadastros de Insumos")
        self.assertContains(response, modelo.nome)
        self.assertContains(response, categoria.nome)
        self.assertContains(response, categoria_maquina.nome)

        modelo_contexto = next(item for item in response.context["modelos"] if item.pk == modelo.pk)
        self.assertEqual(modelo_contexto.total_perguntas, 1)
        self.assertEqual(modelo_contexto.total_registros, 1)

    def test_selecao_de_acompanhamento_filtra_por_categoria(self):
        categoria_a = CategoriaInsumo.objects.create(nome="Lubrificantes")
        categoria_b = CategoriaInsumo.objects.create(nome="Químicos")
        modelo_a = ModeloAuditoria.objects.create(
            nome="Controle de graxa",
            categoria=categoria_a,
            objeto_auditoria="Cadastro para controle da graxa usada na linha A.",
            periodicidade="SEMANAL",
            dia_semana="SEGUNDA",
            ativo=True,
        )
        modelo_b = ModeloAuditoria.objects.create(
            nome="Controle de reagente",
            categoria=categoria_b,
            objeto_auditoria="Cadastro para controle de reagente.",
            periodicidade="SEMANAL",
            dia_semana="TERCA",
            ativo=True,
        )

        response = self.client.get(
            reverse("insumos:selecionar_modelo_preenchimento"),
            {"categoria": categoria_a.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selecionar cadastro para acompanhamento")
        self.assertContains(response, modelo_a.nome)
        self.assertNotContains(response, modelo_b.nome)
        self.assertContains(response, "Iniciar acompanhamento")
