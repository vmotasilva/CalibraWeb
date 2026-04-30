# 📚 Exemplos de Uso - Sistema de Mapeamento de Template

## 1. Criar um Template via Django Shell

```python
from procedures.models import TemplateListaPresenca

# Criar um novo template
template = TemplateListaPresenca.objects.create(
    nome="Template Treinamento Segurança 2024",
    descricao="Template para todos os treinamentos de segurança do trabalho",
    tipo_arquivo="excel",
    metodo_mapeamento="ambos",  # Permitir tanto clique quanto referência
    tem_cabecalho=True,
    num_paginas=1,
    ativo=True
)

print(f"Template criado: {template.nome} (ID: {template.id})")
```

## 2. Fazer Upload de Arquivo Excel

```python
from django.core.files.storage import default_storage
from procedures.models import TemplateListaPresenca

template = TemplateListaPresenca.objects.get(pk=1)

# Se você tem um arquivo
with open('/caminho/para/template.xlsx', 'rb') as f:
    template.arquivo_excel_template.save('template_seguranca.xlsx', f)
    template.save()

print(f"Arquivo salvo em: {template.arquivo_excel_template.url}")
```

## 3. Mapear um Campo Manualmente

```python
from procedures.models import TemplateListaPresenca, MapeamentoCampoListaPresenca

template = TemplateListaPresenca.objects.get(pk=1)

# Mapear o campo "Título do Treinamento" para célula A1
MapeamentoCampoListaPresenca.objects.create(
    template=template,
    tipo_campo="titulo_treinamento",
    localizacao="A1",
    metodo="referencia",
    pagina=1,
    obrigatorio=True,
    permite_imagem_marcacao=False
)

print("Campo mapeado com sucesso!")
```

## 4. Mapear Todos os Campos de Uma Vez

```python
from procedures.models import TemplateListaPresenca, MapeamentoCampoListaPresenca

template = TemplateListaPresenca.objects.get(pk=1)

# Mapear todos os 9 campos obrigatórios
campos_mapeamento = {
    'titulo_treinamento': 'A1',
    'categoria_treinamento': 'A2',
    'metodologia': 'A3',
    'area_conhecimento': 'A4',
    'necessita_avaliacao': 'A5',
    'facilitador_fornecedor': 'A6',
    'data_hora': 'A7',
    'carga_horaria': 'A8',
    'procedimentos_assuntos': 'A9',
}

for tipo_campo, localizacao in campos_mapeamento.items():
    MapeamentoCampoListaPresenca.objects.get_or_create(
        template=template,
        tipo_campo=tipo_campo,
        defaults={
            'localizacao': localizacao,
            'metodo': 'referencia',
            'pagina': 1,
            'obrigatorio': True,
            'permite_imagem_marcacao': False,
        }
    )

print("Todos os campos foram mapeados!")
```

## 5. Verificar Status do Mapeamento

```python
from procedures.models import TemplateListaPresenca

template = TemplateListaPresenca.objects.get(pk=1)

# Verificar se está completo
print(f"Mapeamento completo? {template.mapeamento_completo}")

# Ver quantos campos foram mapeados
mapeados = template.mapeamentos.count()
print(f"Campos mapeados: {mapeados}/9")

# Listar os campos mapeados
for mapeamento in template.mapeamentos.all():
    print(f"  - {mapeamento.get_tipo_campo_display()}: {mapeamento.localizacao}")

# Encontrar campos pendentes
campos_obrigatorios = [
    'titulo_treinamento',
    'categoria_treinamento',
    'metodologia',
    'area_conhecimento',
    'necessita_avaliacao',
    'facilitador_fornecedor',
    'data_hora',
    'carga_horaria',
    'procedimentos_assuntos',
]

mapeados_tipos = set(m.tipo_campo for m in template.mapeamentos.all())
pendentes = [c for c in campos_obrigatorios if c not in mapeados_tipos]

if pendentes:
    print(f"\n⚠️  Campos ainda pendentes:")
    for campo in pendentes:
        print(f"  - {campo}")
```

## 6. Gerar PDF com Mapeamento

```python
from django.http import HttpResponse
from procedures.models import ListaPresenca, TemplateListaPresenca
from procedures.utils.pdf_mapeamento_helper import gerar_lista_presenca_com_mapeamento

# Obter a lista de presença e template
lista = ListaPresenca.objects.get(pk=123)
template = TemplateListaPresenca.objects.get(pk=1)

# Gerar PDF respeitando mapeamento
pdf_buffer = gerar_lista_presenca_com_mapeamento(lista, template)

# Retornar como download
response = HttpResponse(pdf_buffer, content_type='application/pdf')
response['Content-Disposition'] = 'attachment; filename="lista_presenca_' + str(lista.id) + '.pdf"'
return response
```

## 7. Usar em Uma View Django

```python
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from procedures.models import ListaPresenca, TemplateListaPresenca
from procedures.utils.pdf_mapeamento_helper import gerar_lista_presenca_com_mapeamento

@login_required
def gerar_lista_presenca_pdf(request, lista_id, template_id=None):
    """View para gerar PDF com mapeamento de template"""
    
    lista = get_object_or_404(ListaPresenca, pk=lista_id)
    
    if template_id:
        template = get_object_or_404(TemplateListaPresenca, pk=template_id, ativo=True)
    else:
        # Usar template padrão ativo
        template = TemplateListaPresenca.objects.filter(ativo=True).first()
    
    if not template:
        from django.contrib import messages
        messages.error(request, 'Nenhum template ativo disponível')
        return redirect('lista_presenca_detail', pk=lista_id)
    
    try:
        # Gerar PDF
        pdf_buffer = gerar_lista_presenca_com_mapeamento(lista, template)
        
        # Retornar response
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="lista_presenca_{lista.id}.pdf"'
        return response
    
    except Exception as e:
        messages.error(request, f'Erro ao gerar PDF: {str(e)}')
        return redirect('lista_presenca_detail', pk=lista_id)
```

## 8. Chamar API de Preview

```python
import requests
import json

# URL da API
api_url = "http://localhost:8000/procedures/api/template-mapeamento/1/preview-abas/"

# Fazer requisição
response = requests.get(api_url, headers={
    'Authorization': f'Bearer {seu_token}'
})

if response.status_code == 200:
    data = response.json()
    print("Abas disponíveis:")
    for aba in data['abas']:
        print(f"  - {aba['nome']}: {aba['linhas']} linhas, {aba['colunas']} colunas")
else:
    print(f"Erro: {response.status_code}")
    print(response.json())
```

## 9. Chamar API de Preview de Células

```python
import requests

# URL da API com parâmetros
api_url = "http://localhost:8000/procedures/api/template-mapeamento/1/preview-celulas/"
params = {
    'aba': 'Plan1',
    'range': 'A1:D5'
}

response = requests.get(api_url, params=params, headers={
    'Authorization': f'Bearer {seu_token}'
})

if response.status_code == 200:
    data = response.json()
    print(f"Preview da aba {data['aba']}:")
    for linha_info in data['celulas']:
        linha = linha_info['linha']
        print(f"  Linha {linha}:")
        for celula in linha_info['celulas']:
            if celula['valor']:
                print(f"    {celula['ref']}: {celula['valor']}")
```

## 10. Chamar API para Atualizar Campo Mapeado

```python
import requests
import json

# URL da API
api_url = "http://localhost:8000/procedures/api/template-mapeamento/1/atualizar-campo/"

# Dados do campo a mapear
dados = {
    'tipo_campo': 'titulo_treinamento',
    'localizacao': 'B1',  # Mudou de A1 para B1
    'metodo': 'referencia',
    'pagina': 1,
    'obrigatorio': True,
    'permite_imagem_marcacao': False
}

response = requests.post(api_url, data=json.dumps(dados), headers={
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {seu_token}'
})

if response.status_code == 200:
    result = response.json()
    print(result['mensagem'])
else:
    print(f"Erro: {response.status_code}")
```

## 11. Chamar API para Remover Mapeamento

```python
import requests
import json

# URL da API
api_url = "http://localhost:8000/procedures/api/template-mapeamento/1/remover-campo/"

# Campo a remover
dados = {
    'tipo_campo': 'titulo_treinamento'
}

response = requests.post(api_url, data=json.dumps(dados), headers={
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {seu_token}'
})

if response.status_code == 200:
    result = response.json()
    print(result['mensagem'])
```

## 12. Chamar API para Verificar Status

```python
import requests

# URL da API
api_url = "http://localhost:8000/procedures/api/template-mapeamento/1/status/"

response = requests.get(api_url, headers={
    'Authorization': f'Bearer {seu_token}'
})

if response.status_code == 200:
    status = response.json()
    print(f"Mapeamento completo? {status['completo']}")
    print(f"Campos mapeados: {status['campos_mapeados']}/{status['total_campos']}")
    
    if not status['completo']:
        print("\nCampos pendentes:")
        for campo in status['pendentes']:
            print(f"  - {campo}")
    
    print("\nCampos mapeados:")
    for m in status['mapeamentos']:
        print(f"  - {m['tipo_campo']}: {m['localizacao']}")
```

## 13. Workflow Completo em Uma Função

```python
from django.shortcuts import get_object_or_404
from procedures.models import (
    TemplateListaPresenca, MapeamentoCampoListaPresenca, ListaPresenca
)
from procedures.utils.pdf_mapeamento_helper import gerar_lista_presenca_com_mapeamento

def setup_template_e_gerar_pdf(template_id, lista_id):
    """
    Função que faz o workflow completo:
    1. Obtém ou cria template
    2. Verifica se mapeamento está completo
    3. Se não estiver, mapeia campos
    4. Gera PDF com mapeamento
    """
    
    template = get_object_or_404(TemplateListaPresenca, pk=template_id)
    lista = get_object_or_404(ListaPresenca, pk=lista_id)
    
    # Verificar se mapeamento está completo
    if not template.mapeamento_completo:
        print("⚠️  Mapeamento incompleto, completando...")
        
        # Mapear campos padrão
        campos_padrao = {
            'titulo_treinamento': 'A1',
            'categoria_treinamento': 'A2',
            'metodologia': 'A3',
            'area_conhecimento': 'A4',
            'necessita_avaliacao': 'A5',
            'facilitador_fornecedor': 'A6',
            'data_hora': 'A7',
            'carga_horaria': 'A8',
            'procedimentos_assuntos': 'A9',
        }
        
        for tipo, loc in campos_padrao.items():
            MapeamentoCampoListaPresenca.objects.get_or_create(
                template=template,
                tipo_campo=tipo,
                defaults={'localizacao': loc, 'metodo': 'referencia'}
            )
        
        template.mapeamento_completo = True
        template.save()
        print("✅ Mapeamento completado!")
    
    # Gerar PDF
    try:
        pdf = gerar_lista_presenca_com_mapeamento(lista, template)
        print("✅ PDF gerado com sucesso!")
        return pdf
    except Exception as e:
        print(f"❌ Erro ao gerar PDF: {e}")
        return None
```

## 14. Migrar Template de Uma Versão Anterior

```python
from procedures.models import TemplateListaPresenca, MapeamentoCampoListaPresenca

# Se você tinha templates antigos sem mapeamento
templates_antigos = TemplateListaPresenca.objects.filter(
    mapeamento_campos__isnull=True
)

for template in templates_antigos:
    # Criar mapeamento padrão baseado em layout padrão
    campos_default = {
        'titulo_treinamento': 'A1',
        'categoria_treinamento': 'A2',
        'metodologia': 'B1',
        'area_conhecimento': 'B2',
        'necessita_avaliacao': 'C1',
        'facilitador_fornecedor': 'C2',
        'data_hora': 'D1',
        'carga_horaria': 'D2',
        'procedimentos_assuntos': 'E1',
    }
    
    for tipo, loc in campos_default.items():
        MapeamentoCampoListaPresenca.objects.get_or_create(
            template=template,
            tipo_campo=tipo,
            defaults={'localizacao': loc}
        )
    
    # Atualizar JSON também
    template.mapeamento_campos = campos_default
    template.mapeamento_completo = True
    template.save()
    
    print(f"✅ Template '{template.nome}' migrado!")
```

---

## Dicas e Boas Práticas

### ✅ Fazer
- Usar referências de célula (A1, B2) para mapeamentos permanentes
- Validar que arquivo é .xlsx antes de fazer upload
- Testar PDF gerado em diferentes navegadores
- Manter versionamento dos templates importantes
- Documentar layout esperado do Excel

### ❌ Não Fazer
- Não tentar usar arquivos .xls ou .csv
- Não mudar posição de campos após templates em produção
- Não deixar campos sem mapeamento
- Não editar JSON diretamente no BD
- Não deletar templates em uso por listas de presença

### 🔍 Troubleshooting
```python
# Se template não funciona, verificar:

template = TemplateListaPresenca.objects.get(pk=1)

# 1. Arquivo existe?
print(f"Arquivo salvo? {bool(template.arquivo_excel_template)}")

# 2. Todos os campos mapeados?
print(f"Mapeamento completo? {template.mapeamento_completo}")

# 3. Quantos campos foram mapeados?
print(f"Campos mapeados: {template.mapeamentos.count()}/9")

# 4. JSON está bem formado?
print(f"JSON válido? {bool(template.mapeamento_campos)}")
print(template.mapeamento_campos)

# 5. openpyxl está instalado?
try:
    import openpyxl
    print("✅ openpyxl instalado")
except ImportError:
    print("❌ openpyxl não encontrado")
```
