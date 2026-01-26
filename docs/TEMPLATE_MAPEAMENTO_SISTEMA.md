# Sistema de Mapeamento de Template para Lista de Presença

## Visão Geral

O sistema permite que administradores configurem templates reutilizáveis para listas de presença, definindo exatamente onde cada campo de informação será posicionado em um arquivo Excel ou PDF.

## Fluxo de Uso

### 1. Criar Template
- Admin acessa Django Admin > Templates de Lista de Presença
- Clica em "Adicionar Template"
- Preenche: Nome, Descrição, Tipo de Arquivo, Método de Mapeamento

### 2. Upload do Excel
- No detalhe do template, clica em "Upload do Excel"
- Seleciona um arquivo .xlsx em branco (template visual)
- O sistema valida o arquivo (máx 5 MB, formato .xlsx)
- Arquivo é salvo no servidor

### 3. Mapear Campos
- Admin clica em "Mapear Campos"
- Interface mostra:
  - **Painel Esquerdo**: Lista dos 9 campos obrigatórios a mapear
  - **Painel Direito**: Preview do Excel com todas as abas e células
  
#### Dois Métodos de Mapeamento:

**Método 1: Referência de Célula (Recomendado)**
- Admin digita a referência da célula (ex: A1, B5, Z20)
- Formatos válidos: Uma ou duas letras + números
- Exemplos: A1, B10, AA100

**Método 2: Clique Visual**
- Admin clica diretamente na célula do preview do Excel
- O sistema captura a coordenada automaticamente
- Mais intuitivo, mas menos preciso

#### Configuração por Campo:
Cada campo pode ser configurado com:
- **Localização**: Célula do Excel (A1, B2, etc)
- **Página**: Em qual página do PDF/Excel (padrão: 1)
- **Método**: Qual método de definição usar
- **Obrigatório**: Se deve ser validado (padrão: Sim)
- **Permite Imagem**: Se pode receber marcação/assinatura

### 4. Validação
- Sistema valida se todos os 9 campos obrigatórios foram mapeados
- Mostra progresso em tempo real (0/9 até 9/9)
- Barra de progresso visual
- Status "✓ Completo" quando pronto

### 5. Salvar Mapeamento
- Admin clica "Salvar Mapeamento"
- Sistema persiste configuração em banco de dados
- Armazena também em JSON para acesso rápido
- Torna template disponível para gerar listas de presença

## Campos Obrigatórios (9 Total)

1. **Título do Treinamento** - Nome/título da sessão de treinamento
2. **Categoria do Treinamento** - Tipo/categoria do treinamento
3. **Metodologia** - Método utilizado (online, presencial, híbrido)
4. **Área de Conhecimento** - Disciplina/área relacionada
5. **Necessita de Avaliação** - Se há avaliação (Sim/Não)
6. **Facilitador/Fornecedor** - Nome de quem ministra
7. **Data e Hora** - Quando acontece o treinamento
8. **Carga Horária** - Quantas horas de duração
9. **Procedimentos/Assuntos** - Quais procedimentos/temas abordados

## Estrutura de Dados

### Banco de Dados

**Tabela: procedures_templatelistapresenca**
```
- arquivo_excel_template: FileField (arquivo .xlsx salvo)
- metodo_mapeamento: CharField (clique|referencia|ambos)
- mapeamento_campos: JSONField (estrutura dos mapeamentos)
- mapeamento_completo: BooleanField (validação do status)
```

**Tabela: procedures_mapeamentocampolistapresenca**
```
- template: FK para TemplateListaPresenca
- tipo_campo: CharField (um dos 19 tipos disponíveis)
- localizacao: CharField (ex: "A1", "B5")
- metodo: CharField (clique ou referencia)
- pagina: IntegerField (página onde está)
- obrigatorio: BooleanField (é obrigatório?)
- permite_imagem_marcacao: BooleanField (suporta imagem/marca?)
- atualizado_em: DateTimeField (rastreabilidade)
```

### Estrutura JSON (mapeamento_campos)

```json
{
  "titulo_treinamento": {
    "localizacao": "A1",
    "metodo": "referencia",
    "pagina": 1,
    "obrigatorio": true,
    "permite_imagem_marcacao": false
  },
  "categoria_treinamento": {
    "localizacao": "B1",
    "metodo": "referencia",
    "pagina": 1,
    "obrigatorio": true,
    "permite_imagem_marcacao": false
  },
  ...
}
```

## APIs Disponíveis

### 1. Upload do Excel
```
POST /api/template-mapeamento/{pk}/upload/
Content-Type: multipart/form-data

arquivo_excel: <arquivo .xlsx>
```

**Retorna:**
```json
{
  "sucesso": true,
  "mensagem": "Arquivo enviado com sucesso"
}
```

### 2. Preview das Abas
```
GET /api/template-mapeamento/{pk}/preview-abas/
```

**Retorna:**
```json
{
  "abas": [
    {
      "nome": "Plan1",
      "linhas": 50,
      "colunas": 10
    }
  ],
  "aba_ativa": "Plan1"
}
```

### 3. Preview das Células
```
GET /api/template-mapeamento/{pk}/preview-celulas/?aba=Plan1&range=A1:Z50
```

**Retorna:**
```json
{
  "aba": "Plan1",
  "celulas": [
    {
      "linha": 1,
      "celulas": [
        {"ref": "A1", "valor": "Título", "tipo": "str"},
        {"ref": "B1", "valor": "Data", "tipo": "str"}
      ]
    }
  ],
  "total_linhas": 50,
  "total_colunas": 10
}
```

### 4. Atualizar Campo Mapeado
```
POST /api/template-mapeamento/{pk}/atualizar-campo/
Content-Type: application/json

{
  "tipo_campo": "titulo_treinamento",
  "localizacao": "A1",
  "metodo": "referencia",
  "pagina": 1,
  "obrigatorio": true,
  "permite_imagem_marcacao": false
}
```

### 5. Remover Campo Mapeado
```
POST /api/template-mapeamento/{pk}/remover-campo/
Content-Type: application/json

{
  "tipo_campo": "titulo_treinamento"
}
```

### 6. Status do Mapeamento
```
GET /api/template-mapeamento/{pk}/status/
```

**Retorna:**
```json
{
  "total_campos": 9,
  "campos_mapeados": 7,
  "completo": false,
  "pendentes": ["titulo_treinamento", "categoria_treinamento"],
  "mapeamentos": [
    {
      "tipo_campo": "metodologia",
      "localizacao": "C1",
      "metodo": "Referência de Célula (A1)",
      "obrigatorio": true
    }
  ]
}
```

## Geração de PDF

Quando um template é mapeado, ele pode ser usado para gerar PDFs de listas de presença:

```python
from procedures.utils.pdf_mapeamento_helper import gerar_lista_presenca_com_mapeamento

lista = ListaPresenca.objects.get(pk=1)
template = TemplateListaPresenca.objects.get(pk=1)

# Gera PDF respeitando o mapeamento
pdf_buffer = gerar_lista_presenca_com_mapeamento(lista, template)

# Retornar como response
response = HttpResponse(pdf_buffer, content_type='application/pdf')
response['Content-Disposition'] = 'attachment; filename="lista_presenca.pdf"'
return response
```

## Fluxo de Integração com Planejamento

1. Admin cria Planejamento de Treinamento
2. Admin gera Lista de Presença desde Planejamento
3. Sistema oferece opção de usar template mapeado
4. Admin seleciona template
5. Sistema preenche campos conforme mapeamento
6. PDF é gerado com layout customizado

## Validação de Mapeamento

O sistema garante:
- ✅ Arquivo .xlsx válido
- ✅ Todos os 9 campos mapeados
- ✅ Referências de células no formato correto
- ✅ Não há duplicação (um campo por tipo)
- ✅ Páginas estão entre 1-10

## Compatibilidade

- **Django:** 5.0.14
- **Python:** 3.12
- **Biblioteca de Excel:** openpyxl (leitura/escrita de .xlsx)
- **Biblioteca de PDF:** ReportLab (geração de PDFs)

## Exemplos de Uso

### Criar um novo template
```python
from procedures.models import TemplateListaPresenca

template = TemplateListaPresenca.objects.create(
    nome="Template Treinamento Segurança",
    descricao="Template para treinamentos de segurança do trabalho",
    tipo_arquivo="excel",
    metodo_mapeamento="ambos",  # Permite clique E referência
    ativo=True
)
```

### Mapear um campo
```python
from procedures.models import MapeamentoCampoListaPresenca

MapeamentoCampoListaPresenca.objects.create(
    template=template,
    tipo_campo="titulo_treinamento",
    localizacao="A1",
    metodo="referencia",
    pagina=1,
    obrigatorio=True,
    permite_imagem_marcacao=False
)
```

### Verificar status de mapeamento
```python
status = template.mapeamento_completo  # Boolean
pendentes = [m.tipo_campo for m in template.mapeamentos.all()]
campos_obrigatorios = ['titulo_treinamento', 'categoria_treinamento', ...]
nao_mapeados = [c for c in campos_obrigatorios if c not in pendentes]
```

## Troubleshooting

### Erro: "Arquivo muito grande"
- Verifique se o arquivo tem mais de 5 MB
- Simplifique o template removendo imagens grandes

### Erro: "Apenas arquivos .xlsx são aceitos"
- Salve como ".xlsx" no Excel (não ".xls" ou ".csv")
- Use Arquivo > Salvar Como > Formato Excel Moderno

### Erro: "openpyxl não está instalado"
- Execute: `pip install openpyxl`
- Ou execute o setup: `python manage.py setup_dependencies`

### Mapeamento não é exibido
- Verifique se template.arquivo_excel_template está salvo
- Confirme se template.mapeamentos.all() retorna registros

## Melhorias Futuras

- [ ] Preview de PDF antes de salvar mapeamento
- [ ] Importar mapeamento de template existente
- [ ] Duplicar template com mapeamento
- [ ] Histórico de versões do mapeamento
- [ ] Validação de dados antes de gerar PDF
- [ ] Suporte a múltiplas planilhas com mapeamentos diferentes
- [ ] Export/Import de mapeamento como arquivo de configuração
