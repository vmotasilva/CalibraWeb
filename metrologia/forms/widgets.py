# -*- coding: utf-8 -*-
"""
Widgets customizados para forms de Metrologia
"""

from django import forms
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from metrologia.models import Instrumento


class InstrumentosModalWidget(forms.Widget):
    """Widget que permite seleção de instrumentos via modal com tabela filtrada."""
    
    template_name = 'metrologia/widgets/instrumentos_modal_widget.html'
    
    def __init__(self, dias_vencimento=None, attrs=None):
        """Inicializa o widget com número de dias opcional."""
        super().__init__(attrs)
        self.dias_vencimento = dias_vencimento or 30
    
    def render(self, name, value, attrs=None, renderer=None):
        """Renderiza o widget com campo hidden e botão para abrir modal."""
        from metrologia.models import CategoriaInstrumento
        from organization.models import Setor
        from datetime import date, timedelta

        if value is None:
            value = []
        elif isinstance(value, str):
            # Se vier como string separada por vírgula
            value = [v.strip() for v in value.split(',') if v.strip().isdigit()]
        elif isinstance(value, list):
            value = [str(v) for v in value if str(v).strip().isdigit()]
        else:
            value = [str(value)] if str(value).strip().isdigit() else []

        selected_instruments = Instrumento.objects.filter(id__in=value)
        all_instruments = Instrumento.objects.filter(ativo=True).select_related('categoria', 'setor').order_by('tag')

        # Listas para filtros
        categorias = CategoriaInstrumento.objects.all().order_by('nome')
        setores = Setor.objects.all().order_by('nome')

        # Calcula status de vencimento para cada instrumento
        hoje = date.today()
        dias_limite = self.dias_vencimento
        data_limite = hoje + timedelta(days=dias_limite)
        
        instrumentos_info = []
        for inst in all_instruments:
            if inst.data_proxima_calibracao:
                if inst.data_proxima_calibracao < hoje:
                    venc_status = 'vencido'
                elif inst.data_proxima_calibracao <= data_limite:
                    venc_status = 'vencendo'
                else:
                    venc_status = 'ok'
            else:
                venc_status = 'sem_data'
            
            # Filtra apenas instrumentos vencidos ou vencendo no período
            if venc_status in ['vencido', 'vencendo']:
                tratativa = getattr(inst, 'tratativa_calibracao', 'INTERNA')
                instrumentos_info.append({
                    'id': inst.id,
                    'tag': inst.tag,
                    'descricao': inst.descricao,
                    'categoria': inst.categoria.nome if inst.categoria else '',
                    'categoria_id': inst.categoria.id if inst.categoria else '',
                    'setor': inst.setor.nome if inst.setor else '',
                    'setor_id': inst.setor.id if inst.setor else '',
                    'vencimento': inst.data_proxima_calibracao,
                    'venc_status': venc_status,
                    'tratativa': tratativa,
                })

        context = {
            'name': name,
            'selected_ids': [str(v) for v in value],
            'selected_instruments': selected_instruments,
            'all_instruments': all_instruments,
            'categorias': categorias,
            'setores': setores,
            'instrumentos_info': instrumentos_info,
            'dias_vencimento': dias_limite,
        }
        return mark_safe(render_to_string(self.template_name, context))
    
    def value_from_datadict(self, data, files, name):
        """Extrai os valores selecionados do formulário."""
        # Os valores vêm como uma lista JSON codificada em um input hidden
        values = data.getlist(f'{name}_ids')
        return values if values else []
