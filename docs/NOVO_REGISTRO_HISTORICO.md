# Novo Recurso: Botão para Adicionar Registro na Listagem de Históricos

## Resumo da Implementação

Foi adicionado um botão **"Novo Registro"** na página de listagem de históricos de calibração (`/qms/metrologia/historicos/`) que permite criar um novo registro de forma rápida e intuitiva.

## Componentes Implementados

### 1. **Botão na Listagem** (`qms/templates/qms/historicos_calibracao_list.html`)
- Botão azul com ícone `bi-plus-circle` na seção superior da página
- Localização: ao lado do botão "Voltar"
- Função: abre um modal com a seleção de instrumento

### 2. **Modal de Seleção** (`qms/templates/qms/historicos_calibracao_list.html`)
- **ID**: `novoRegistroModal`
- **Funcionalidades**:
  - Campo de busca para filtrar instrumentos
  - Lista de instrumentos com tag, descrição e categoria
  - Clique em um instrumento para prosseguir
  - Busca em tempo real (sem necessidade de botão)

**Dados Exibidos**:
- `tag`: Identificador do instrumento
- `descricao`: Descrição completa
- `categoria`: Categoria do instrumento

**Funcionalidade de Busca**:
- Filtra por tag, descrição ou categoria
- Case-insensitive
- Atualiza instantaneamente enquanto você digita

### 3. **Nova View** (`qms/views.py`)
```python
def novo_historico_calibracao_from_listagem_view(request, instrumento_id)
```

**Funcionalidades**:
- Valida que o instrumento existe e está ativo
- Cria um novo `HistoricoCalibracao` com valores padrão:
  - `data_calibracao`: Data de hoje
  - `data_aprovacao`: Data de hoje
  - `numero_certificado`: "S/N" (a ser preenchido)
  - `tipo_calibracao`: "EXTERNA" (padrão)
  - `resultado`: "APROVADO_SEM_CORRECAO" (padrão)
- Redireciona imediatamente para a tela de edição (`editar_historico_calibracao`)
- Exibe mensagem de sucesso

**Tratamento de Erros**:
- Se o instrumento não existe ou está inativo: redireciona para listagem com mensagem de erro
- Logs de erro no servidor para debugging

### 4. **Rota URL** (`qms/urls.py`)
```
Path: /qms/metrologia/novo-registro/<instrumento_id>/
Name: novo_historico_from_listagem
```

### 5. **Contexto atualizado** (`qms/views.py` - `listar_historicos_calibracao_view`)
- Adicionado `instrumentos_json`: String JSON com lista de instrumentos ativos
- Formato dos dados:
  ```json
  [
    {
      "id": 123,
      "tag": "TH-01",
      "descricao": "Termômetro Digital",
      "categoria": "Termometria"
    }
  ]
  ```

## Fluxo de Uso

1. **Usuário está na página de Históricos** (`/qms/metrologia/historicos/`)
2. **Clica no botão "Novo Registro"**
   - Modal de seleção é exibido
   - Focus automático no campo de busca
3. **Busca ou seleciona um instrumento**
   - Digita na busca para filtrar
   - Ou rolando a lista
   - Clica no instrumento desejado
4. **Sistema cria o registro**
   - Novo `HistoricoCalibracao` é criado
   - Redireciona para a tela de edição
   - Mensagem de sucesso é exibida
5. **Usuário edita os dados**
   - Preenche data, certificado, resultado, etc.
   - Salva o registro

## Detalhes Técnicos

### Segurança
- `@login_required`: Apenas usuários autenticados podem acessar
- Validação de instrumento ativo
- Tratamento de exceções com logging

### Performance
- Dados dos instrumentos carregados uma única vez (ao abrir o modal)
- Busca em cliente (no navegador) para rapidez
- JSON renderizado diretamente no template (sem requisição AJAX extra)

### Compatibilidade
- Bootstrap 5 (modal, botões, grid)
- Bootstrap Icons (ícones)
- JavaScript vanilla (sem jQuery)
- Suporta navegadores modernos

## Alterações de Arquivo

### Modificados:
1. `qms/templates/qms/historicos_calibracao_list.html`
   - Botão "Novo Registro"
   - Modal com seleção de instrumento
   - Script JavaScript para busca e seleção

2. `qms/views.py`
   - Nova view: `novo_historico_calibracao_from_listagem_view()`
   - Contexto atualizado: `instrumentos_json`

3. `qms/urls.py`
   - Nova rota para a view

### Não modificados:
- Modelos de dados (HistoricoCalibracao, Instrumento)
- Comportamento existente de listagem
- Tela de edição de registros

## Mensagens do Usuário

### Sucesso
```
✓ Novo registro criado para [TAG]! Preencha os dados.
```

### Erro (instrumento não encontrado)
```
Instrumento não encontrado ou inativo.
```

### Erro (exceção genérica)
```
Erro ao criar registro: [detalhes do erro]
```

## Próximos Passos Opcionais

- Adicionar botão "Novo Instrumento" direto no modal (se necessário)
- Ordenação customizada na lista (por categoria, por data de última calibração, etc.)
- Pré-seleção baseada em filtros aplicados
- Histórico de instrumentos frequentemente usados
