# -*- coding: utf-8 -*-
"""
Views para Gerenciamento e Upload de Templates de Treinamento
Permite upload, download, ativação e organização de modelos de documentos (.xlsx, .docx, .pdf)
"""

import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404, JsonResponse
from django.db import transaction
from procedures.models import TemplateDocumentoTreinamento


# Guia de Tags de Referência para Orientação do Usuário
TAGS_REFERENCIA = {
    'LISTA_PRESENCA': [
        {'tag': '{{TITULO}}', 'descricao': 'Título do Treinamento ou Sessão'},
        {'tag': '{{INSTRUTOR}}', 'descricao': 'Nome Completo do Instrutor'},
        {'tag': '{{DATA_HORA}}', 'descricao': 'Data e Horário Previsto (ex: DD/MM/YYYY HH:MM)'},
        {'tag': '{{CARGA_HORARIA}}', 'descricao': 'Carga Horária (ex: 60 Minutos)'},
        {'tag': '{{NOME_PARTICIPANTE}}', 'descricao': 'Âncora para o Nome do Colaborador (Linha do loop)'},
        {'tag': '{{MATRICULA_PARTICIPANTE}}', 'descricao': 'Matrícula do Colaborador (Linha do loop)'},
        {'tag': '{{SETOR_PARTICIPANTE}}', 'descricao': 'Setor do Colaborador (Linha do loop)'},
        {'tag': '{{PROCEDIMENTOS}}', 'descricao': 'Âncora para Lista de Procedimentos no Verso (Código - Nome)'},
        {'tag': '{{CHK_TREIN}}', 'descricao': 'Marcação Unicode (●/○) para Tipo Treinamento'},
        {'tag': '{{CHK_REUN}}', 'descricao': 'Marcação Unicode (●/○) para Tipo Reunião'},
        {'tag': '{{CHK_RECIC}}', 'descricao': 'Marcação Unicode (●/○) para Reciclagem'},
        {'tag': '{{CHK_INTEGRACAO}}', 'descricao': 'Marcação Unicode (●/○) para Integração'},
        {'tag': '{{CHK_LOFT}}', 'descricao': 'Marcação Unicode (●/○) para Metodologia Prática / LOFT'},
        {'tag': '{{CHK_TRAD}}', 'descricao': 'Marcação Unicode (●/○) para Metodologia Tradicional'},
        {'tag': '{{CHK_AVAL_SIM}}', 'descricao': 'Marcação Unicode (●/○) para Necessita Avaliação: SIM'},
        {'tag': '{{CHK_AVAL_NAO}}', 'descricao': 'Marcação Unicode (●/○) para Necessita Avaliação: NÃO'},
        {'tag': '{{CHK_QUALIDADE}}', 'descricao': 'Marcação Unicode (●/○) para Área Qualidade/SGQ'},
        {'tag': '{{CHK_ADM}}', 'descricao': 'Marcação Unicode (●/○) para Área Administrativa'},
        {'tag': '{{CHK_PRODUCAO}}', 'descricao': 'Marcação Unicode (●/○) para Área de Produção'},
        {'tag': '{{CHK_OPERACIONAL}}', 'descricao': 'Marcação Unicode (●/○) para Área Técnica/Operacional'},
    ],
    'AVALIACAO_EFICACIA': [
        {'tag': '{{TITULO}}', 'descricao': 'Título do Treinamento Avaliado'},
        {'tag': '{{COLABORADOR}}', 'descricao': 'Nome do Colaborador Avaliado'},
        {'tag': '{{MATRICULA}}', 'descricao': 'Matrícula do Colaborador'},
        {'tag': '{{AVALIADOR}}', 'descricao': 'Líder / Supervisor Avaliador'},
        {'tag': '{{DATA_AVALIACAO}}', 'descricao': 'Data da Realização da Avaliação'},
        {'tag': '{{STATUS_EFICACIA}}', 'descricao': 'Resultado da Eficácia (Eficaz / Não Eficaz)'},
        {'tag': '{{NOTAS}}', 'descricao': 'Pontuação obtida nas competências avaliadas'},
        {'tag': '{{OBSERVACOES}}', 'descricao': 'Parecer técnico / Justificativa do avaliador'},
    ],
    'CERTIFICADO': [
        {'tag': '{{NOME_ALUNO}}', 'descricao': 'Nome Completo do Aluno/Colaborador'},
        {'tag': '{{CURSO_NOME}}', 'descricao': 'Nome / Título do Treinamento'},
        {'tag': '{{CARGA_HORARIA}}', 'descricao': 'Carga Horária Total'},
        {'tag': '{{DATA_CONCLUSAO}}', 'descricao': 'Data de Conclusão do Treinamento'},
        {'tag': '{{INSTRUTOR_NOME}}', 'descricao': 'Nome e Assinatura do Instrutor'},
        {'tag': '{{CODIGO_VALIDACAO}}', 'descricao': 'Código Único de Rastreabilidade / Autenticidade'},
    ],
    'INTEGRACAO': [
        {'tag': '{{NOME_COLABORADOR}}', 'descricao': 'Nome do Novo Colaborador'},
        {'tag': '{{SETOR}}', 'descricao': 'Setor / Departamento de Lotação'},
        {'tag': '{{CARGO}}', 'descricao': 'Cargo do Colaborador'},
        {'tag': '{{DATA_ADMISSAO}}', 'descricao': 'Data de Início da Integração'},
        {'tag': '{{ITENS_INTEGRACAO}}', 'descricao': 'Lista de Módulos e Procedimentos de Integração'},
    ],
    'OUTROS': [
        {'tag': '{{TITULO}}', 'descricao': 'Título Genérico do Documento'},
        {'tag': '{{DATA}}', 'descricao': 'Data Atual'},
        {'tag': '{{RESPONSAVEL}}', 'descricao': 'Nome do Usuário Emissor'},
    ]
}


@login_required
def templates_config_list_view(request):
    """Página principal de gerenciamento de templates de treinamentos."""
    templates = TemplateDocumentoTreinamento.objects.select_related('criado_por').all()
    
    # Filtro por função
    funcao_filtro = request.GET.get('funcao', '')
    if funcao_filtro:
        templates = templates.filter(funcao=funcao_filtro)

    # Estatísticas
    total_templates = TemplateDocumentoTreinamento.objects.count()
    total_ativos = TemplateDocumentoTreinamento.objects.filter(ativo=True).count()
    funcoes_choices = TemplateDocumentoTreinamento.FUNCAO_CHOICES
    tipos_choices = TemplateDocumentoTreinamento.TIPO_ARQUIVO_CHOICES

    context = {
        'templates': templates,
        'total_templates': total_templates,
        'total_ativos': total_ativos,
        'funcoes_choices': funcoes_choices,
        'tipos_choices': tipos_choices,
        'funcao_filtro': funcao_filtro,
        'tags_referencia': TAGS_REFERENCIA,
    }
    return render(request, 'procedures/templates_config.html', context)


@login_required
def template_config_upload_view(request):
    """Processa o upload de um novo template de documento."""
    if request.method != 'POST':
        return redirect('procedures:templates_config')

    codigo = request.POST.get('codigo', '').strip()
    nome = request.POST.get('nome', '').strip()
    funcao = request.POST.get('funcao', 'LISTA_PRESENCA')
    tipo_arquivo = request.POST.get('tipo_arquivo', 'xlsx')
    descricao = request.POST.get('descricao', '').strip()
    definir_ativo = request.POST.get('ativo') == 'on'
    arquivo = request.FILES.get('arquivo')

    if not codigo or not nome or not arquivo:
        messages.error(request, '⚠️ Código, Nome e Arquivo são obrigatórios para cadastrar um template.')
        return redirect('procedures:templates_config')

    # Validação da extensão do arquivo
    ext = os.path.splitext(arquivo.name)[1].lower().replace('.', '')
    if ext not in ['xlsx', 'docx', 'pdf']:
        messages.error(request, f'⚠️ Formato de arquivo .{ext} não é suportado. Envie arquivos .xlsx, .docx ou .pdf.')
        return redirect('procedures:templates_config')

    with transaction.atomic():
        # Se este template for definido como ativo, desativa os outros da mesma função
        if definir_ativo:
            TemplateDocumentoTreinamento.objects.filter(funcao=funcao).update(ativo=False)

        template = TemplateDocumentoTreinamento.objects.create(
            codigo=codigo,
            nome=nome,
            funcao=funcao,
            tipo_arquivo=tipo_arquivo,
            descricao=descricao,
            arquivo=arquivo,
            ativo=definir_ativo,
            criado_por=request.user
        )

    messages.success(request, f'✅ Template "{template.codigo} - {template.nome}" cadastrado com sucesso!')
    return redirect('procedures:templates_config')


@login_required
def template_config_toggle_active_view(request, template_id):
    """Alterna o status ativo/padrão do template."""
    template = get_object_or_404(TemplateDocumentoTreinamento, id=template_id)
    
    with transaction.atomic():
        if not template.ativo:
            # Desativa outros da mesma função e ativa este
            TemplateDocumentoTreinamento.objects.filter(funcao=template.funcao).update(ativo=False)
            template.ativo = True
            template.save(update_fields=['ativo', 'atualizado_em'])
            messages.success(request, f'🌟 Template "{template.codigo}" agora é o padrão ativo para {template.get_funcao_display()}.')
        else:
            template.ativo = False
            template.save(update_fields=['ativo', 'atualizado_em'])
            messages.info(request, f'Template "{template.codigo}" desativado.')

    return redirect('procedures:templates_config')


@login_required
def template_config_download_view(request, template_id):
    """Permite fazer o download do arquivo do template armazenado."""
    template = get_object_or_404(TemplateDocumentoTreinamento, id=template_id)
    
    if not template.arquivo or not os.path.exists(template.arquivo.path):
        messages.error(request, '⚠️ O arquivo físico do template não foi encontrado no servidor.')
        return redirect('procedures:templates_config')

    with open(template.arquivo.path, 'rb') as f:
        file_data = f.read()

    content_types = {
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'pdf': 'application/pdf',
    }
    content_type = content_types.get(template.tipo_arquivo, 'application/octet-stream')
    
    response = HttpResponse(file_data, content_type=content_type)
    filename = os.path.basename(template.arquivo.name)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def template_config_delete_view(request, template_id):
    """Exclui um template do sistema."""
    template = get_object_or_404(TemplateDocumentoTreinamento, id=template_id)
    
    if request.method == 'POST':
        nome_template = str(template)
        # Apagar o arquivo físico se existir
        if template.arquivo and os.path.exists(template.arquivo.path):
            try:
                os.remove(template.arquivo.path)
            except Exception:
                pass
        template.delete()
        messages.success(request, f'🗑️ Template "{nome_template}" removido com sucesso.')
    
    return redirect('procedures:templates_config')
