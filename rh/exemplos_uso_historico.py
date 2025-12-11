"""
Exemplo de Uso - Sistema de Histórico de Colaboradores

Copie e adapte este código em suas views ou scripts para registrar mudanças.
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from datetime import date

from rh.models import Colaborador
from rh.utils_historico import GerenciadorHistoricoColaborador


# ============================================================================
# EXEMPLO 1: View para editar dados do colaborador com histórico automático
# ============================================================================

@login_required
@require_http_methods(["POST"])
def atualizar_colaborador(request, colab_id):
    """
    View que atualiza dados do colaborador e registra mudanças no histórico
    """
    colaborador = Colaborador.objects.get(id=colab_id)
    
    # Dados antigos
    setor_antigo = colaborador.setor
    cargo_antigo = colaborador.cargo
    salario_antigo = colaborador.salario
    
    # Dados novos do formulário
    novo_setor_id = request.POST.get('setor')
    novo_cargo = request.POST.get('cargo')
    novo_salario = request.POST.get('salario')
    motivo = request.POST.get('motivo')
    data_efetiva = request.POST.get('data_efetiva')
    
    # Atualizar colaborador
    if novo_setor_id:
        from organization.models import Setor
        novo_setor = Setor.objects.get(id=novo_setor_id)
        colaborador.setor = novo_setor
        
        # Registrar mudança de setor
        GerenciadorHistoricoColaborador.registrar_mudanca_setor(
            colaborador=colaborador,
            setor_novo=novo_setor,
            motivo=motivo or f"Alterado de {setor_antigo}",
            usuario=request.user,
            data_efetiva=date.fromisoformat(data_efetiva) if data_efetiva else date.today()
        )
    
    if novo_cargo:
        colaborador.cargo = novo_cargo
        
        # Registrar mudança de cargo
        GerenciadorHistoricoColaborador.registrar_mudanca_cargo(
            colaborador=colaborador,
            cargo_novo=novo_cargo,
            motivo=motivo or f"Alterado de {cargo_antigo}",
            usuario=request.user,
            data_efetiva=date.fromisoformat(data_efetiva) if data_efetiva else date.today()
        )
    
    if novo_salario:
        novo_salario = float(novo_salario)
        colaborador.salario = novo_salario
        
        # Registrar mudança de salário
        GerenciadorHistoricoColaborador.registrar_mudanca_salario(
            colaborador=colaborador,
            salario_novo=novo_salario,
            motivo=motivo or f"Alterado de R$ {salario_antigo}",
            usuario=request.user,
            data_efetiva=date.fromisoformat(data_efetiva) if data_efetiva else date.today()
        )
    
    # Salvar colaborador
    colaborador.save()
    
    messages.success(request, "Colaborador atualizado com sucesso! Histórico registrado.")
    return redirect('detalhe_colaborador', colab_id=colab_id)


# ============================================================================
# EXEMPLO 2: View para consultar histórico de um colaborador
# ============================================================================

@login_required
def historico_colaborador(request, colab_id):
    """
    View que exibe o histórico completo de um colaborador com filtros
    """
    colaborador = Colaborador.objects.get(id=colab_id)
    
    # Obter histórico
    historico_geral = colaborador.get_historico_completo()
    
    # Filtrar por tipo se solicitado
    tipo_mudanca = request.GET.get('tipo')
    if tipo_mudanca:
        historico_geral = historico_geral.filter(tipo_mudanca=tipo_mudanca)
    
    # Contexto para o template
    context = {
        'colaborador': colaborador,
        'historico': historico_geral,
        'tipos_mudanca': [
            ('SETOR', 'Mudança de Setor'),
            ('CARGO', 'Mudança de Cargo'),
            ('SALARIO', 'Mudança de Salário'),
            ('TURNO', 'Mudança de Turno'),
            ('STATUS', 'Mudança de Status'),
        ],
        'resumo': {
            'ultima_mudanca_setor': colaborador.get_ultimo_setor_historico(),
            'ultima_mudanca_cargo': colaborador.get_ultimo_cargo_historico(),
            'ultima_mudanca_salario': colaborador.get_ultimo_salario_historico(),
            'total_mudancas': historico_geral.count(),
        }
    }
    
    return render(request, 'rh/historico_colaborador.html', context)


# ============================================================================
# EXEMPLO 3: Script de management command para importar histórico
# ============================================================================

"""
Criar arquivo em: rh/management/commands/importar_historico.py

from django.core.management.base import BaseCommand
from datetime import date
from rh.models import Colaborador
from rh.utils_historico import GerenciadorHistoricoColaborador

class Command(BaseCommand):
    help = 'Importa histórico de mudanças de um arquivo CSV'

    def add_arguments(self, parser):
        parser.add_argument('arquivo', type=str, help='Caminho do arquivo CSV')

    def handle(self, *args, **options):
        import csv
        
        arquivo = options['arquivo']
        with open(arquivo, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                colaborador = Colaborador.objects.get(matricula=row['matricula'])
                
                # Registrar mudança baseada no tipo
                if row['tipo'] == 'SETOR':
                    from organization.models import Setor
                    novo_setor = Setor.objects.get(nome=row['valor_novo'])
                    GerenciadorHistoricoColaborador.registrar_mudanca_setor(
                        colaborador=colaborador,
                        setor_novo=novo_setor,
                        motivo=row.get('motivo', ''),
                        data_efetiva=date.fromisoformat(row['data'])
                    )
                
                # ... similar para CARGO, SALARIO, etc
        
        self.stdout.write(self.style.SUCCESS('Histórico importado com sucesso!'))

# Executar com:
# python manage.py importar_historico caminho/do/arquivo.csv
"""


# ============================================================================
# EXEMPLO 4: Comparativo de dados (antes/depois)
# ============================================================================

def comparativo_historico(request, hist_id):
    """
    View que exibe um comparativo visual das mudanças
    """
    from rh.models import HistoricoColaborador
    
    historico = HistoricoColaborador.objects.get(id=hist_id)
    
    # Formatar dados para exibição
    comparativo = {
        'tipo': historico.get_tipo_mudanca_display(),
        'data': historico.data_mudanca,
        'data_efetiva': historico.data_efetiva,
        'descricao': historico.descricao,
        'dados_anteriores': historico.dados_anteriores,
        'dados_novos': historico.dados_novos,
        'aprovado': historico.aprovado,
        'aprovado_por': historico.aprovado_por,
    }
    
    return render(request, 'rh/comparativo_historico.html', {'comparativo': comparativo})


# ============================================================================
# EXEMPLO 5: Relatório de movimentação por período
# ============================================================================

def relatorio_movimentacao(request):
    """
    View que gera relatório de mudanças de pessoal por período
    """
    from datetime import datetime, timedelta
    from rh.models import HistoricoColaborador
    
    # Data inicial (últimos 30 dias)
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    if not data_inicio:
        data_inicio = (datetime.now() - timedelta(days=30)).date()
    else:
        data_inicio = date.fromisoformat(data_inicio)
    
    if not data_fim:
        data_fim = datetime.now().date()
    else:
        data_fim = date.fromisoformat(data_fim)
    
    # Filtrar mudanças por período
    mudancas = HistoricoColaborador.objects.filter(
        data_mudanca__range=[data_inicio, data_fim]
    ).order_by('-data_mudanca')
    
    # Agrupar por tipo
    resumo = {
        'SETOR': mudancas.filter(tipo_mudanca='SETOR').count(),
        'CARGO': mudancas.filter(tipo_mudanca='CARGO').count(),
        'SALARIO': mudancas.filter(tipo_mudanca='SALARIO').count(),
        'TURNO': mudancas.filter(tipo_mudanca='TURNO').count(),
        'STATUS': mudancas.filter(tipo_mudanca='STATUS').count(),
    }
    
    context = {
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'mudancas': mudancas,
        'resumo': resumo,
        'total': mudancas.count(),
    }
    
    return render(request, 'rh/relatorio_movimentacao.html', context)
