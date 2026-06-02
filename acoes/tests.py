import uuid
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from organization.models import Setor
from rh.models import Colaborador

from acoes.models import (
    AcaoCorretiva,
    KPIOpcao,
    LinhaAcao,
    OrigemProblema,
    PlanoAcao,
    RevisaoGerencial,
    Solucao,
    Solucao8D,
    SolucaoA3,
    SolucaoGestaoDeMudanca,
    SolucaoRNC,
    TipoSolucao,
)


def unique_text(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def date_input(days=0):
    return (timezone.localdate() + timedelta(days=days)).strftime("%Y-%m-%d")


def datetime_input(days=0):
    value = timezone.localtime(timezone.now() + timedelta(days=days)).replace(second=0, microsecond=0)
    return value.strftime("%Y-%m-%dT%H:%M")


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username=unique_text("testuser"),
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def setor(db):
    return Setor.objects.create(nome=unique_text("Setor"))


@pytest.fixture
def colaborador(db, setor):
    return Colaborador.objects.create(
        matricula=unique_text("MAT"),
        nome_completo="Maria Tester",
        grupo="Qualidade",
        setor=setor,
    )


def create_acao(colaborador, **overrides):
    data = {
        "numero_registro": unique_text("AC"),
        "titulo": "Ação corretiva teste",
        "descricao": "Descrição da ação teste",
        "tipo": "corretiva",
        "tipo_solucao": "melhoria",
        "status": "aberta",
        "data_abertura": timezone.localdate(),
        "data_vencimento": timezone.localdate() + timedelta(days=15),
        "criado_por": colaborador,
        "responsavel": colaborador,
        "ativo": True,
    }
    data.update(overrides)
    return AcaoCorretiva.objects.create(**data)


def create_solucao(colaborador, tipo, **overrides):
    acao = overrides.pop("acao_corretiva", None) or create_acao(colaborador, tipo_solucao=tipo)
    data = {
        "acao_corretiva": acao,
        "tipo": tipo,
        "titulo": f"Solução {tipo}",
        "descricao": f"Descrição {tipo}",
        "responsavel": colaborador,
    }
    data.update(overrides)
    return Solucao.objects.create(**data)


def create_plano_acao(colaborador, **overrides):
    solucao = overrides.pop("solucao", None) or create_solucao(colaborador, "plano_acao")
    data = {
        "solucao": solucao,
        "numero_registro": unique_text("PA"),
        "numero_acao": 1,
        "descricao": "Plano de ação de teste",
        "problema": "Problema de teste",
        "status": "planejada",
        "classificacao": "melhoria",
        "responsavel_acao": colaborador,
        "data_primeira_deadline": timezone.localdate() + timedelta(days=7),
        "data_deadline": timezone.localdate() + timedelta(days=14),
        "prioridade": True,
    }
    data.update(overrides)
    return PlanoAcao.objects.create(**data)


def create_a3(colaborador, **overrides):
    solucao = overrides.pop("solucao", None) or create_solucao(colaborador, "a3")
    data = {
        "solucao": solucao,
        "a3_numero": unique_text("A3"),
        "data_criacao": timezone.localdate(),
        "laboratorio": "CQ",
        "lider_projeto": colaborador,
        "problema": "Problema A3",
        "objetivo": "Objetivo A3",
        "estado_atual": "Estado atual",
        "resultados": "Resultados",
    }
    data.update(overrides)
    return SolucaoA3.objects.create(**data)


def create_8d(colaborador, **overrides):
    solucao = overrides.pop("solucao", None) or create_solucao(colaborador, "8d")
    data = {
        "solucao": solucao,
        "numero_formulario": unique_text("8D"),
        "data_abertura": timezone.now(),
        "lider_8d": colaborador,
        "departamento": "Qualidade",
        "problema_identificado": "Problema 8D",
        "d2_descricao": "Descrição 8D",
    }
    data.update(overrides)
    return Solucao8D.objects.create(**data)


def create_rnc(colaborador, **overrides):
    solucao = overrides.pop("solucao", None) or create_solucao(colaborador, "rnc")
    data = {
        "solucao": solucao,
        "numero_rnc": unique_text("RNC"),
        "data_abertura": timezone.now(),
        "origem": "processo",
        "classificacao": "maior",
        "descricao_nc": "Descrição da não conformidade",
        "risco": "alto",
        "responsavel": colaborador,
    }
    data.update(overrides)
    return SolucaoRNC.objects.create(**data)


def create_mudanca(colaborador, **overrides):
    solucao = overrides.pop("solucao", None) or create_solucao(colaborador, "gestao_mudanca")
    data = {
        "solucao": solucao,
        "numero_registro": unique_text("GM"),
        "data_abertura": timezone.now(),
        "solicitante": "Roberto Alves",
        "tipo_mudanca": "qms_sgi",
        "prioridade_mudanca": "medio",
        "situacao_antes": "Antes",
        "situacao_depois": "Depois",
        "justificativa": "Justificativa",
        "status": "analise",
    }
    data.update(overrides)
    return SolucaoGestaoDeMudanca.objects.create(**data)


def create_revisao(colaborador, **overrides):
    solucao = overrides.pop("solucao", None) or create_solucao(colaborador, "revisao_gerencial")
    data = {
        "solucao": solucao,
        "numero_rg": unique_text("RG"),
        "data_realizacao": timezone.localdate(),
        "laboratorio": "CQ",
        "periodo_inicio": "2026-01-01",
        "periodo_fim": "2026-03-31",
        "representante_direcao": "Diretoria",
        "responsavel_unidade": "Gerência",
        "analises_criticas": "Análises críticas",
        "status": "planejada",
    }
    data.update(overrides)
    return RevisaoGerencial.objects.create(**data)


def plano_create_payload(colaborador):
    return {
        "numero_registro": unique_text("PA"),
        "numero_acao": 1,
        "descricao": "Implementar novo fluxo",
        "problema": "Fluxo atual sem rastreabilidade",
        "classificacao": "melhoria",
        "status": "planejada",
        "prioridade": "on",
        "responsavel_acao": colaborador.pk,
        "data_primeira_deadline": date_input(5),
        "data_deadline": date_input(10),
        "comentarios": "Criado via teste",
        "resultado": "Resultado esperado",
    }


def a3_payload(colaborador):
    return {
        "a3_numero": unique_text("A3"),
        "data_criacao": date_input(),
        "laboratorio": "CQ",
        "lider_projeto": colaborador.pk,
        "participantes": "Equipe A3",
        "problema": "Problema A3",
        "historico_importancia": "Histórico",
        "observacoes_importantes": "Observações",
        "analise_causas": "Análise",
        "causa_raiz": "Causa raiz",
        "objetivo": "Objetivo",
        "estado_atual": "Estado atual",
        "resultados": "Resultados",
    }


def oito_d_payload(colaborador):
    return {
        "numero_formulario": unique_text("8D"),
        "data_abertura": datetime_input(),
        "lider_8d": colaborador.pk,
        "departamento": "Qualidade",
        "problema_identificado": "Problema 8D",
        "prazo_projeto": date_input(30),
        "d2_descricao": "Descrição 8D",
        "d3_contencao": "Contenção",
        "d4_causa_raiz": "Causa raiz",
        "d5_contramedidas": "Contramedidas",
        "d6_implementacao": "Implementação",
        "d6_status": "implementada",
    }


def rnc_payload(colaborador):
    return {
        "unidade": "CQ",
        "numero_rnc": unique_text("RNC"),
        "data_abertura": datetime_input(),
        "origem": "processo",
        "classificacao": "maior",
        "descricao_nc": "Descrição da NC",
        "evidencia_nc": "Evidência",
        "frequencia": "frequente",
        "risco": "alto",
        "causa_raiz": "Causa raiz",
        "acao_contencao": "Ação de contenção",
        "acao_nc": "corrigir",
        "eficacia": "eficaz",
        "responsavel": colaborador.pk,
        "analise_causas": "Análise",
        "acao_imediata": "Ação imediata",
        "acao_corretiva": "Ação corretiva",
        "acao_preventiva": "Ação preventiva",
        "plano_verificacao": "Plano de verificação",
        "resultado": "Resultado",
    }


def mudanca_payload():
    return {
        "unidade": "CQ",
        "data_abertura": datetime_input(),
        "solicitante": "Roberto Alves",
        "numero_registro": unique_text("GM"),
        "tipo_mudanca": "qms_sgi",
        "prioridade_mudanca": "medio",
        "area_impactada": "Qualidade",
        "area_avaliadora": "Validação",
        "situacao_antes": "Antes",
        "situacao_depois": "Depois",
        "justificativa": "Justificativa",
        "beneficios": "Benefícios",
        "data_mudanca": date_input(15),
        "impacto_pessoas": "Nenhum",
        "referencia_pessoas": "baixo",
        "impacto_ambiente": "Nenhum",
        "referencia_ambiente": "baixo",
        "impacto_ativos": "Controlado",
        "referencia_ativos": "baixo",
        "impacto_compliance": "Sem impacto",
        "referencia_compliance": "baixo",
        "processos_afetados": "Processo X",
        "status": "analise",
    }


def revisao_payload():
    return {
        "numero_rg": unique_text("RG"),
        "data_realizacao": date_input(),
        "laboratorio": "CQ",
        "periodo_inicio": "2026-01-01",
        "periodo_fim": "2026-03-31",
        "representante_direcao": "Diretoria",
        "responsavel_unidade": "Gerência",
        "participantes": "Time da revisão",
        "entradas_acompanhamento": "Entradas",
        "entradas_auditorias": "Auditorias",
        "entradas_satisfacao": "Satisfação",
        "entradas_desempenho": "Desempenho",
        "entradas_pessoal": "Pessoal",
        "entradas_fornecedores": "Fornecedores",
        "entradas_mudancas": "Mudanças",
        "entradas_risco": "Riscos",
        "entradas_oportunidades": "Oportunidades",
        "saidas_eficacia_sgq": "Saídas SGQ",
        "saidas_melhoria_produto": "Saídas produto",
        "saidas_necessidades_cliente": "Saídas cliente",
        "saidas_necessidade_recurso": "Saídas recursos",
        "analises_criticas": "Análises críticas",
        "status": "planejada",
    }


@pytest.mark.django_db
def test_salvar_acao_corretiva_modal_cria_e_atualiza_registro(auth_client, colaborador):
    payload = {
        "data_abertura": date_input(),
        "ano": timezone.localdate().year,
        "unidade": "CQ",
        "numero_registro": unique_text("AC"),
        "tipo_solucao": "RNC",
        "origem": "Auditoria",
        "descricao": "Descrição modal",
        "causa_raiz": "Causa raiz",
        "responsavel": colaborador.pk,
        "data_vencimento": date_input(7),
        "status": "aberta",
    }

    response = auth_client.post(reverse("acoes:salvar_acao_corretiva_modal"), payload)
    assert response.status_code == 200
    assert response.json()["success"] is True
    acao = AcaoCorretiva.objects.get()
    assert acao.titulo == payload["numero_registro"]

    update_payload = payload | {"id": acao.pk, "descricao": "Descrição atualizada"}
    response = auth_client.post(reverse("acoes:salvar_acao_corretiva_modal"), update_payload)
    assert response.status_code == 200
    acao.refresh_from_db()
    assert acao.descricao == "Descrição atualizada"


@pytest.mark.django_db
def test_listar_acoes_filtra_atrasadas_e_resume_linhas(auth_client, colaborador):
    acao = create_acao(
        colaborador,
        status="em_progresso",
        data_vencimento=timezone.localdate() - timedelta(days=2),
    )
    solucao = create_solucao(colaborador, "plano_acao", acao_corretiva=acao)
    plano = create_plano_acao(colaborador, solucao=solucao)
    LinhaAcao.objects.create(
        plano_acao=plano,
        numero_acao=1,
        descricao="Ação filha",
        status="planejada",
        responsavel_acao=colaborador,
    )

    response = auth_client.get(reverse("acoes:listar_acoes"), {"status": "atrasada"})
    assert response.status_code == 200
    assert len(response.context["acoes"]) == 1
    assert response.context["acoes"][0].status == "atrasada"
    assert "Planejada: 1" in response.context["acoes"][0].acoes_status_resumo


@pytest.mark.django_db
def test_listar_acoes_usa_consulta_relacional(auth_client, colaborador):
    create_acao(colaborador, status="aberta")

    response = auth_client.get(reverse("acoes:listar_acoes"))

    assert response.status_code == 200
    assert len(response.context["acoes"]) == 1
    assert response.context["acoes"][0].status == "aberta"


@pytest.mark.django_db
def test_detalhe_acao_exibe_plano_e_linhas(auth_client, colaborador):
    acao = create_acao(colaborador)
    solucao = create_solucao(colaborador, "plano_acao", acao_corretiva=acao)
    plano = create_plano_acao(colaborador, solucao=solucao)
    linha = LinhaAcao.objects.create(
        plano_acao=plano,
        numero_acao=1,
        descricao="Linha detalhada",
        status="em_curso",
        responsavel_acao=colaborador,
    )

    response = auth_client.get(reverse("acoes:detalhe_acao", args=[acao.pk]))
    assert response.status_code == 200
    assert response.context["plano_acao"] == plano
    assert list(response.context["acoes_associadas"]) == [linha]


@pytest.mark.django_db
def test_plano_acao_create_view_cria_solucao_base(auth_client, colaborador):
    response = auth_client.post(reverse("acoes:plano_acao_create"), plano_create_payload(colaborador))
    assert response.status_code == 302
    assert response.headers["Location"].endswith(reverse("acoes:plano_acao_list"))

    plano = PlanoAcao.objects.get()
    assert plano.solucao_id is not None
    assert plano.solucao.acao_corretiva_id is not None
    assert plano.numero_registro


@pytest.mark.django_db
def test_plano_acao_list_update_detail_delete_flow(auth_client, colaborador):
    plano = create_plano_acao(colaborador)

    list_response = auth_client.get(reverse("acoes:plano_acao_list"))
    assert list_response.status_code == 200
    assert plano in list_response.context["object_list"]

    detail_response = auth_client.get(reverse("acoes:plano_acao_detail", args=[plano.pk]))
    assert detail_response.status_code == 200
    assert detail_response.context["object"] == plano

    payload = plano_create_payload(colaborador) | {"numero_registro": plano.numero_registro, "numero_acao": plano.numero_acao}
    payload["descricao"] = "Plano atualizado"
    response = auth_client.post(reverse("acoes:plano_acao_update", args=[plano.pk]), payload)
    assert response.status_code == 302
    plano.refresh_from_db()
    assert plano.descricao == "Plano atualizado"

    response = auth_client.post(reverse("acoes:plano_acao_delete", args=[plano.pk]))
    assert response.status_code == 302
    assert PlanoAcao.objects.count() == 0


CREATE_SCENARIOS = [
    ("acoes:a3_create", "acoes:a3_list", SolucaoA3, a3_payload, "a3_numero"),
    ("acoes:8d_create", "acoes:8d_list", Solucao8D, oito_d_payload, "numero_formulario"),
    ("acoes:rnc_create", "acoes:rnc_list", SolucaoRNC, rnc_payload, "numero_rnc"),
    ("acoes:gestao_mudanca_create", "acoes:gestao_mudanca_list", SolucaoGestaoDeMudanca, mudanca_payload, "numero_registro"),
    ("acoes:revisao_gerencial_create", "acoes:revisao_gerencial_list", RevisaoGerencial, revisao_payload, "numero_rg"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("create_url,list_url,model,payload_factory,identifier_field", CREATE_SCENARIOS)
def test_create_views_criam_registro_com_solucao_base(auth_client, colaborador, create_url, list_url, model, payload_factory, identifier_field):
    payload = payload_factory(colaborador) if payload_factory in {a3_payload, oito_d_payload, rnc_payload} else payload_factory()
    response = auth_client.post(reverse(create_url), payload)

    assert response.status_code == 302
    assert response.headers["Location"].endswith(reverse(list_url))

    obj = model.objects.get()
    assert getattr(obj, identifier_field)
    assert obj.solucao_id is not None
    assert obj.solucao.acao_corretiva_id is not None


UPDATE_DETAIL_SCENARIOS = [
    (
        "acoes:a3_list",
        "acoes:a3_detail",
        "acoes:a3_update",
        create_a3,
        lambda colaborador, obj: a3_payload(colaborador) | {"a3_numero": obj.a3_numero, "problema": "Problema atualizado"},
        "problema",
        "Problema atualizado",
    ),
    (
        "acoes:8d_list",
        "acoes:8d_detail",
        "acoes:8d_update",
        create_8d,
        lambda colaborador, obj: oito_d_payload(colaborador) | {"numero_formulario": obj.numero_formulario, "problema_identificado": "Problema 8D atualizado"},
        "problema_identificado",
        "Problema 8D atualizado",
    ),
    (
        "acoes:rnc_list",
        "acoes:rnc_detail",
        "acoes:rnc_update",
        create_rnc,
        lambda colaborador, obj: rnc_payload(colaborador) | {"numero_rnc": obj.numero_rnc, "descricao_nc": "NC atualizada"},
        "descricao_nc",
        "NC atualizada",
    ),
    (
        "acoes:gestao_mudanca_list",
        "acoes:gestao_mudanca_detail",
        "acoes:gestao_mudanca_update",
        create_mudanca,
        lambda colaborador, obj: mudanca_payload() | {"numero_registro": obj.numero_registro, "justificativa": "Justificativa atualizada"},
        "justificativa",
        "Justificativa atualizada",
    ),
    (
        "acoes:revisao_gerencial_list",
        "acoes:revisao_gerencial_detail",
        "acoes:revisao_gerencial_update",
        create_revisao,
        lambda colaborador, obj: revisao_payload() | {"numero_rg": obj.numero_rg, "analises_criticas": "Análise crítica atualizada"},
        "analises_criticas",
        "Análise crítica atualizada",
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize("list_url,detail_url,update_url,factory,payload_factory,field_name,expected_value", UPDATE_DETAIL_SCENARIOS)
def test_list_detail_update_views_dos_tipos_de_solucao(auth_client, colaborador, list_url, detail_url, update_url, factory, payload_factory, field_name, expected_value):
    obj = factory(colaborador)

    list_response = auth_client.get(reverse(list_url))
    assert list_response.status_code == 200
    assert obj in list_response.context["object_list"]

    detail_response = auth_client.get(reverse(detail_url, args=[obj.pk]))
    assert detail_response.status_code == 200
    assert detail_response.context["object"] == obj

    response = auth_client.post(reverse(update_url, args=[obj.pk]), payload_factory(colaborador, obj))
    assert response.status_code == 302
    obj.refresh_from_db()
    assert getattr(obj, field_name) == expected_value


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name,expected_template",
    [
        ("acoes:plano_acao_create", "planoacao_form_table.html"),
        ("acoes:a3_create", "solucaoa3_form.html"),
        ("acoes:8d_create", "solucao8d_form.html"),
        ("acoes:rnc_create", "solucaornc_form.html"),
        ("acoes:gestao_mudanca_create", "solucaogesta_de_mudanca_form.html"),
        ("acoes:revisao_gerencial_create", "revisaogerencial_form.html"),
    ],
)
def test_create_views_renderizam_templates_atuais(auth_client, url_name, expected_template):
    response = auth_client.get(reverse(url_name))
    assert response.status_code == 200
    assert any((template.name or '').endswith(expected_template) for template in response.templates)


REFERENCE_SCENARIOS = [
    (OrigemProblema, "acoes:origem_problema_list", "acoes:origem_problema_create", "acoes:origem_problema_update", "acoes:origem_problema_delete", {"nome": unique_text("Origem"), "descricao": "Origem teste", "codigo": unique_text("OP"), "ativo": True}, "nome"),
    (KPIOpcao, "acoes:kpi_opcao_list", "acoes:kpi_opcao_create", "acoes:kpi_opcao_update", "acoes:kpi_opcao_delete", {"nome": unique_text("KPI"), "descricao": "KPI teste", "codigo": unique_text("KPI"), "ativo": True}, "nome"),
    (TipoSolucao, "acoes:tipo_solucao_list", "acoes:tipo_solucao_create", "acoes:tipo_solucao_update", "acoes:tipo_solucao_delete", {"nome": unique_text("Tipo"), "descricao": "Tipo teste", "ativo": True}, "nome"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("model,list_url,create_url,update_url,delete_url,payload,field_name", REFERENCE_SCENARIOS)
def test_reference_views_crud(auth_client, model, list_url, create_url, update_url, delete_url, payload, field_name):
    create_response = auth_client.post(reverse(create_url), payload)
    assert create_response.status_code == 302

    obj = model.objects.get()
    list_response = auth_client.get(reverse(list_url))
    assert list_response.status_code == 200
    assert obj in list_response.context["object_list"]

    updated_value = unique_text("Atualizado")
    update_payload = payload | {field_name: updated_value}
    update_response = auth_client.post(reverse(update_url, args=[obj.pk]), update_payload)
    assert update_response.status_code == 302
    obj.refresh_from_db()
    assert getattr(obj, field_name) == updated_value

    delete_response = auth_client.post(reverse(delete_url, args=[obj.pk]))
    assert delete_response.status_code == 302
    assert model.objects.count() == 0


@pytest.mark.django_db
def test_dashboard_e_api_proximo_numero(auth_client, colaborador):
    create_acao(colaborador, status="em_progresso")
    create_plano_acao(colaborador, numero_acao=1)
    create_a3(colaborador, numero_acao=1)
    create_8d(colaborador, numero_acao=1)
    create_rnc(colaborador)
    create_mudanca(colaborador)
    create_revisao(colaborador)

    dashboard = auth_client.get(reverse("acoes:dashboard"))
    assert dashboard.status_code == 200
    assert dashboard.context["total_planos"] >= 1
    assert dashboard.context["total_a3s"] >= 1
    assert dashboard.context["total_8ds"] >= 1

    invalid = auth_client.get(reverse("acoes:obter_proximo_numero"))
    assert invalid.status_code == 400

    valid = auth_client.get(reverse("acoes:obter_proximo_numero"), {"tipo": "plano_acao"})
    assert valid.status_code == 200
    payload = valid.json()
    assert payload["tipo"] == "plano_acao"
    assert payload["proximo_numero"] == "002"