# GUIA PARA PRÓXIMAS TAREFAS (Forms + Templates)

## 🎯 Visão Geral

Agora que os modelos Django estão 100% alinhados com os templates Excel, o próximo passo é criar Forms Django e atualizar os Templates HTML para refletir essa estrutura.

## 📋 Checklist de Tarefas Restantes

### Tarefa 6: Criar Django Forms
- [ ] 6.1 - PlanoAcaoForm
- [ ] 6.2 - SolucaoRNCForm
- [ ] 6.3 - SolucaoGestaoDeMudancaForm
- [ ] 6.4 - Solucao8DForm (multi-step)

### Tarefa 7: Atualizar Templates HTML
- [ ] 7.1 - Template do PlanoAcaoForm
- [ ] 7.2 - Template do SolucaoRNCForm
- [ ] 7.3 - Template do SolucaoGestaoDeMudancaForm
- [ ] 7.4 - Template do Solucao8DForm
- [ ] 7.5 - JavaScript para interatividade

### Tarefa 8: Testes & Validação
- [ ] 8.1 - Testes unitários dos models
- [ ] 8.2 - Testes dos forms
- [ ] 8.3 - Testes de integração
- [ ] 8.4 - Teste de performance
- [ ] 8.5 - Validação com dados reais

---

## 📝 TAREFA 6: CRIAR DJANGO FORMS

### 6.1 PlanoAcaoForm

```python
# acoes/forms.py

from django import forms
from .models import PlanoAcao, Colaborador

class PlanoAcaoForm(forms.ModelForm):
    """Form para Plano de Ação com validações específicas"""
    
    class Meta:
        model = PlanoAcao
        fields = [
            'numero_acao',
            'laboratorio_area_projeto',
            'numero_registro',
            'input_origem',
            'problema',
            'laboratorio',
            'kpi',
            'descricao',
            'classificacao',
            'status',
            'prioridade',
            'responsavel_acao',
            'data_primeira_deadline',
            'data_deadline',
            'comentarios',
            'acao_eficaz',
            'resultado',
        ]
        widgets = {
            'numero_acao': forms.NumberInput(attrs={'class': 'form-control'}),
            'laboratorio_area_projeto': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_registro': forms.TextInput(attrs={'class': 'form-control'}),
            'input_origem': forms.TextInput(attrs={'class': 'form-control'}),
            'problema': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'laboratorio': forms.TextInput(attrs={'class': 'form-control'}),
            'kpi': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'classificacao': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'prioridade': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'responsavel_acao': forms.ModelChoiceField(
                queryset=Colaborador.objects.all(),
                widget=forms.Select(attrs={'class': 'form-control'})
            ),
            'data_primeira_deadline': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'data_deadline': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'comentarios': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'acao_eficaz': forms.Select(attrs={'class': 'form-control'}),
            'resultado': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validação: Primeira deadline não pode ser depois de deadline final
        primeira_deadline = cleaned_data.get('data_primeira_deadline')
        deadline = cleaned_data.get('data_deadline')
        
        if primeira_deadline and deadline:
            if primeira_deadline > deadline:
                raise forms.ValidationError(
                    "Primeira deadline deve ser anterior ou igual à deadline final."
                )
        
        # Validação: Eficácia só pode ser preenchida se status for concluída
        status = cleaned_data.get('status')
        acao_eficaz = cleaned_data.get('acao_eficaz')
        
        if acao_eficaz and status != 'completa':
            raise forms.ValidationError(
                "Ação Eficaz deve ser preenchida apenas quando status é 'Completa'."
            )
        
        return cleaned_data
```

### 6.2 SolucaoRNCForm

```python
class SolucaoRNCForm(forms.ModelForm):
    """Form para RNC com gerenciamento de risco integrado"""
    
    class Meta:
        model = SolucaoRNC
        fields = [
            'numero_rnc',
            'unidade',
            'data_abertura',
            'origem',
            'classificacao',
            'requerimento_requisito',
            'descricao_nc',
            'evidencia_nc',
            'frequencia',
            'risco',
            'causa_raiz',
            'acao_contencao',
            'acao_nc',
            'gerar_plano_acao',
            'plano_acao_relacionado',
            'acao_imediata',
            'acao_corretiva',
            'acao_preventiva',
            'analise_causas',
            'plano_verificacao',
            'resultado',
            'eficacia',
            'evidencia_implementacao',
            'responsavel',
            'data_fechamento',
        ]
        widgets = {
            # ... configurar widgets conforme acima ...
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validação: RNC Crítica com Risco Alto requer Ação de Contenção
        classificacao = cleaned_data.get('classificacao')
        risco = cleaned_data.get('risco')
        acao_contencao = cleaned_data.get('acao_contencao')
        
        if classificacao == 'critica' and risco == 'alto':
            if not acao_contencao:
                raise forms.ValidationError(
                    "RNC Crítica com Risco Alto requer Ação de Contenção!"
                )
        
        return cleaned_data
```

### 6.3 SolucaoGestaoDeMudancaForm

```python
class SolucaoGestaoDeMudancaForm(forms.ModelForm):
    """Form para Gestão de Mudança com seção EHS"""
    
    class Meta:
        model = SolucaoGestaoDeMudanca
        fields = [
            # Informações Gerais
            'unidade', 'solicitante', 'data_abertura', 'numero_registro',
            'tipo_mudanca', 'prioridade_mudanca', 'area_impactada', 'area_avaliadora',
            
            # Dados da Mudança
            'situacao_antes', 'situacao_depois', 'justificativa', 'beneficios',
            'data_mudanca', 'evidencia',
            
            # EHS
            'impacto_pessoas', 'referencia_pessoas',
            'impacto_ambiente', 'referencia_ambiente',
            'impacto_ativos', 'referencia_ativos',
            'impacto_compliance', 'referencia_compliance',
            
            # Riscos
            'processos_afetados', 'modulos_sistema_afetados', 'como_afeta_processo',
            'consequencia_nao_mudanca', 'riscos_identificados', 'tratamento_riscos',
            'plano_contingencia', 'areas_implantacao', 'observacoes',
            
            # Plano
            'gerar_plano_acao', 'plano_acao_relacionado', 'percentual_conclusao_plano',
            
            # Análise Crítica
            'sera_implantada', 'solicitante_informado', 'data_informada',
            'justificativa_area1', 'responsavel_decisao_area1', 'data_area1',
            'justificativa_area2', 'responsavel_decisao_area2', 'data_area2',
            
            # Status
            'status', 'plano_validacao', 'resultado_validacao',
        ]
        
        fieldsets = (
            ('Informações Gerais', {
                'fields': ('unidade', 'solicitante', 'data_abertura', 'numero_registro',
                          'tipo_mudanca', 'prioridade_mudanca', 'area_impactada', 'area_avaliadora')
            }),
            ('Dados da Mudança', {
                'fields': ('situacao_antes', 'situacao_depois', 'justificativa', 
                          'beneficios', 'data_mudanca', 'evidencia')
            }),
            ('Impactos de EHS', {
                'fields': ('impacto_pessoas', 'referencia_pessoas',
                          'impacto_ambiente', 'referencia_ambiente',
                          'impacto_ativos', 'referencia_ativos',
                          'impacto_compliance', 'referencia_compliance')
            }),
            # ... mais fieldsets ...
        )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validação: Se EHS está marcado, precisa ter referência
        if any([cleaned_data.get(f'impacto_{p}') 
                for p in ['pessoas', 'ambiente', 'ativos', 'compliance']]):
            
            if not any([cleaned_data.get(f'referencia_{p}') 
                       for p in ['pessoas', 'ambiente', 'ativos', 'compliance']]):
                raise forms.ValidationError(
                    "Se há impacto EHS, deve ser definida referência!"
                )
        
        return cleaned_data
```

### 6.4 Solucao8DForm (Multi-Step)

```python
class Solucao8DFormD1(forms.ModelForm):
    """Form D1 - Formação da Equipe"""
    
    class Meta:
        model = Solucao8D
        fields = [
            'numero_formulario', 'data_abertura', 'lider_8d', 'patrocinador',
            'equipe', 'departamento', 'problema_identificado', 'prazo_projeto'
        ]

class Solucao8DFormD2(forms.ModelForm):
    """Form D2 - Descrever o Problema"""
    
    class Meta:
        model = Solucao8D
        fields = ['d2_descricao', 'd2_especificacoes']

class Solucao8DFormD3(forms.ModelForm):
    """Form D3 - Conter o Problema"""
    
    class Meta:
        model = Solucao8D
        fields = ['d3_contencao', 'd3_responsavel', 'd3_deadline']

# ... continue para D4-D8 ...
```

---

## 🎨 TAREFA 7: ATUALIZAR TEMPLATES HTML

### 7.1 Template PlanoAcaoForm

**Arquivo:** `acoes/templates/acoes/planoacao_form.html`

```html
{% extends "base.html" %}
{% load crispy_forms_tags %}

{% block title %}Plano de Ação{% endblock %}

{% block content %}
<div class="container-fluid mt-4">
    <div class="row">
        <div class="col-12">
            <h1>{{ object|default:"Novo Plano de Ação" }}</h1>
            <hr>
        </div>
    </div>
    
    <form method="post" class="form-horizontal" id="planoacao-form">
        {% csrf_token %}
        
        <!-- NAVEGAÇÃO POR ABAS/SEÇÕES -->
        <ul class="nav nav-tabs" role="tablist">
            <li class="nav-item">
                <a class="nav-link active" data-toggle="tab" href="#identificacao">Identificação</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" data-toggle="tab" href="#acao">Ação</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" data-toggle="tab" href="#status">Status & Prazos</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" data-toggle="tab" href="#resultado">Resultado</a>
            </li>
        </ul>
        
        <!-- CONTEÚDO DAS ABAS -->
        <div class="tab-content mt-3">
            <!-- IDENTIFICAÇÃO -->
            <div id="identificacao" class="tab-pane fade show active">
                <div class="row">
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.numero_acao %}
                    </div>
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.numero_registro %}
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-12">
                        {% include "form_field.html" with field=form.laboratorio_area_projeto %}
                    </div>
                </div>
            </div>
            
            <!-- AÇÃO -->
            <div id="acao" class="tab-pane fade">
                <div class="row">
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.input_origem %}
                    </div>
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.laboratorio %}
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.problema %}
                    </div>
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.kpi %}
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-12">
                        {% include "form_field.html" with field=form.descricao %}
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.classificacao %}
                    </div>
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.responsavel_acao %}
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-12">
                        {% include "form_field.html" with field=form.comentarios %}
                    </div>
                </div>
            </div>
            
            <!-- STATUS & PRAZOS -->
            <div id="status" class="tab-pane fade">
                <div class="row">
                    <div class="col-md-4">
                        {% include "form_field.html" with field=form.status %}
                    </div>
                    <div class="col-md-4">
                        {% include "form_field.html" with field=form.prioridade %}
                    </div>
                    <div class="col-md-4">
                        <!-- Progress bar -->
                        <div class="form-group">
                            <label>Percentual de Conclusão</label>
                            <div class="progress">
                                <div id="progress-bar" class="progress-bar" role="progressbar" 
                                     style="width: 0%">0%</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.data_primeira_deadline %}
                    </div>
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.data_deadline %}
                    </div>
                </div>
            </div>
            
            <!-- RESULTADO -->
            <div id="resultado" class="tab-pane fade">
                <div class="row">
                    <div class="col-md-6">
                        {% include "form_field.html" with field=form.acao_eficaz %}
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-12">
                        {% include "form_field.html" with field=form.resultado %}
                    </div>
                </div>
            </div>
        </div>
        
        <!-- BOTÕES -->
        <div class="row mt-4">
            <div class="col-12">
                <button type="submit" class="btn btn-primary">Salvar</button>
                <a href="{% url 'acoes:listar_solucoes' %}" class="btn btn-secondary">Cancelar</a>
            </div>
        </div>
    </form>
</div>

<script>
    // Atualizar percentual de conclusão quando status muda
    document.getElementById('id_status').addEventListener('change', function() {
        const status = this.value;
        const statusWeights = {
            'planejada': 0,
            'em_curso': 50,
            'completa': 100,
            'retardo': 25,
            'cancelada': 0
        };
        
        const percentage = statusWeights[status] || 0;
        const progressBar = document.getElementById('progress-bar');
        progressBar.style.width = percentage + '%';
        progressBar.textContent = percentage + '%';
    });
    
    // Trigger initial calculation
    document.getElementById('id_status').dispatchEvent(new Event('change'));
</script>
{% endblock %}
```

---

## 🧪 TAREFA 8: TESTES

### 8.1 Testes Unitários

```python
# tests/test_models_excel_alignment.py

from django.test import TestCase
from acoes.models import PlanoAcao, SolucaoRNC, SolucaoGestaoDeMudanca, Solucao8D
from rh.models import Colaborador

class PlanoAcaoModelTest(TestCase):
    """Testar alinhamento do PlanoAcao com Excel"""
    
    def setUp(self):
        self.colaborador = Colaborador.objects.create_user(
            email='test@test.com',
            nome_completo='Teste Usuario'
        )
    
    def test_percentual_conclusao_planejada(self):
        """Ação planejada = 0%"""
        pa = PlanoAcao.objects.create(
            status='planejada',
            descricao='Test'
        )
        self.assertEqual(pa.percentual_conclusao(), 0)
    
    def test_percentual_conclusao_completa(self):
        """Ação completa = 100%"""
        pa = PlanoAcao.objects.create(
            status='completa',
            descricao='Test'
        )
        self.assertEqual(pa.percentual_conclusao(), 100)
    
    def test_status_choices_alinhado_com_excel(self):
        """Status choices devem incluir valores do Excel"""
        expected_statuses = ['planejada', 'em_curso', 'completa', 'retardo', 'cancelada']
        actual_statuses = [choice[0] for choice in PlanoAcao.STATUS_CHOICES]
        for status in expected_statuses:
            self.assertIn(status, actual_statuses)

# ... mais testes ...
```

---

## 📚 Referências

- Modelos: `/acoes/models.py`
- Admin: `/acoes/admin.py`
- Excel: `/acoes/Excel/*.xlsx`
- Análise: `/ANALISE_EXCEL_TEMPLATES.md`
- Comparação: `/COMPARACAO_CAMPOS_ANTES_DEPOIS.md`

---

**Próximos Passos:** Iniciar Tarefa 6 (Forms Django)
