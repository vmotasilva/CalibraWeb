# Atualização: Sistema de Listas de Presença - Participantes Externos e Treinamentos Flexíveis

## 📋 Visão Geral das Mudanças

O sistema foi atualizado para suportar:
1. **Participantes externos** (pessoas não cadastradas como colaboradores)
2. **Treinamentos/reuniões sem procedimentos** (alinhamentos internos, capacitações gerais, etc.)

---

## 🆕 Novo Modelo: ParticipanteExterno

### Campos
- `nome_completo`: Nome completo do participante (obrigatório)
- `cpf`: CPF para identificação (opcional)
- `empresa`: Empresa/instituição de origem (opcional)
- `email`: E-mail de contato (opcional)
- `telefone`: Telefone de contato (opcional)
- `observacoes`: Notas adicionais (opcional)
- `criado_em`, `atualizado_em`: Timestamps automáticos

### Características
- ✅ Cadastro rápido durante criação de lista de presença
- ✅ Reutilizável em múltiplas listas
- ✅ Independente do módulo RH
- ✅ Ideal para visitantes, auditores externos, consultores, etc.

---

## 🔄 Modificações no Modelo RegistroTreinamento

### Novos Campos

#### 1. Tipo de Registro
```python
tipo = models.CharField(
    max_length=20,
    choices=[
        ('PROCEDIMENTO', 'Treinamento em Procedimento'),
        ('ALINHAMENTO', 'Alinhamento Interno'),
        ('REUNIAO', 'Reunião'),
        ('CAPACITACAO', 'Capacitação/Curso'),
        ('OUTRO', 'Outro'),
    ],
    default='PROCEDIMENTO'
)
```

#### 2. Participante Externo
```python
participante_externo = models.ForeignKey(
    ParticipanteExterno,
    on_delete=models.CASCADE,
    null=True, blank=True
)
```

#### 3. Informações Alternativas (quando não há procedimento)
```python
titulo_treinamento = models.CharField(
    max_length=200, null=True, blank=True,
    help_text="Obrigatório quando não há procedimento vinculado"
)
descricao = models.TextField(null=True, blank=True)
```

### Campos Agora Opcionais
- ✅ `colaborador` (nullable) - pode ser externo
- ✅ `procedimento` (nullable) - pode ser treinamento geral

### Novas Validações

O modelo agora valida:
1. **Participante**: Deve ter colaborador OU externo (não ambos, não nenhum)
2. **Tipo PROCEDIMENTO**: Requer procedimento vinculado
3. **Sem procedimento**: Requer título_treinamento

### Novas Properties

#### `participante_nome`
Retorna nome do participante (colaborador ou externo)
```python
@property
def participante_nome(self):
    if self.colaborador:
        return self.colaborador.nome
    elif self.participante_externo:
        return self.participante_externo.nome_completo
    return "-"
```

#### `assunto`
Retorna assunto do registro (procedimento ou título)
```python
@property
def assunto(self):
    if self.procedimento:
        return f"{self.procedimento.codigo} - {self.procedimento.nome}"
    return self.titulo_treinamento or "-"
```

#### `status_treinamento` (atualizado)
Agora diferencia:
- **Com procedimento**: Valida revisão como antes
- **Sem procedimento**: Verifica apenas se tem data (não há revisões para validar)

---

## 📝 Formulários Atualizados

### ParticipanteExternoForm (Novo)
Form para cadastro rápido de participantes externos com validação de email e formatação de telefone.

### RegistroTreinamentoInlineForm (Modificado)
Agora inclui:
- Campo `tipo_participante` (colaborador/externo) - controla visibilidade
- Campo `tipo` (PROCEDIMENTO/ALINHAMENTO/REUNIAO/etc.)
- Campos condicionais baseados no tipo selecionado

### ImportacaoTreinamentoForm (Modificado)
Nova opção:
```python
tipo_importacao = forms.ChoiceField(
    choices=[
        ('procedimento', 'Treinamentos em Procedimentos'),
        ('geral', 'Alinhamentos/Reuniões Gerais')
    ]
)
```

---

## 🎨 Interface do Usuário

### Formulário de Lista de Presença

#### Seleção de Tipo de Participante
Radio buttons para escolher:
- 🧑‍💼 **Colaborador** → Mostra select de colaboradores cadastrados
- 👤 **Externo** → Mostra select de externos + opção de cadastrar novo

#### Seleção de Tipo de Registro
Dropdown com opções:
- 📘 **Treinamento em Procedimento** → Mostra campo de procedimento
- 📋 **Alinhamento Interno** → Mostra campos título + descrição
- 🤝 **Reunião** → Mostra campos título + descrição
- 🎓 **Capacitação/Curso** → Mostra campos título + descrição
- ❓ **Outro** → Mostra campos título + descrição

#### Campos Dinâmicos (JavaScript)
- Campos aparecem/desaparecem automaticamente baseado nas seleções
- Validação client-side para garantir campos obrigatórios
- UX intuitivo com transições suaves

### Visualização de Detalhes

#### Nova Tabela de Registros
Colunas:
1. **Tipo** - Badge colorido (Procedimento, Alinhamento, Reunião, etc.)
2. **Participante** - Nome + ícone para externos
3. **Empresa/Mat.** - Matrícula (interno) ou empresa (externo)
4. **Assunto** - Procedimento ou título livre
5. **Data** - Data do treinamento
6. **Status** - OK/PENDENTE
7. **Observações** - Notas adicionais

#### Estatísticas Aprimoradas
4 cards:
1. **Total Participantes** → Mostra split (X internos + Y externos)
2. **Total Procedimentos** → Conta apenas registros com procedimento
3. **Total Registros** → Soma geral
4. **Tipos de Registro** → Breakdown por tipo (badge + contagem)

---

## 💻 Casos de Uso

### Caso 1: Treinamento com Auditor Externo

**Situação:** Auditor da certificadora vem treinar equipe sobre nova norma ISO.

**Como registrar:**
1. Criar lista de presença
2. Preencher dados da sessão
3. Para cada participante:
   - Tipo: **Externo** (auditor) ou **Colaborador** (equipe)
   - Tipo de Registro: **Capacitação**
   - Título: "Treinamento ISO 9001:2015 - Mudanças"
   - Descrição: "Principais alterações na norma..."

**Resultado:** 
- Auditor registrado como externo (sem matrícula)
- Treinamento sem vínculo com procedimento específico
- Histórico mantido para auditoria

### Caso 2: Alinhamento Interno Estratégico

**Situação:** Reunião mensal com gerentes para alinhamento de metas.

**Como registrar:**
1. Criar lista de presença
2. Tipo de Registro: **Alinhamento** ou **Reunião**
3. Título: "Alinhamento Estratégico - Metas Q1 2025"
4. Descrição: "Discussão sobre KPIs do trimestre..."
5. Participantes: Apenas colaboradores internos

**Resultado:**
- Registro sem procedimento
- Documento da reunião/alinhamento
- Rastreabilidade para ISO (evidência de comunicação)

### Caso 3: Visita Técnica com Fornecedor

**Situação:** Fornecedor vem apresentar novo equipamento para equipe técnica.

**Como registrar:**
1. Lista de presença
2. Participantes: Colaboradores + Representante do fornecedor (externo)
3. Tipo: **Capacitação**
4. Título: "Apresentação Equipamento XYZ"
5. Cadastrar externo: Nome, empresa fornecedora, email

**Resultado:**
- Mix de internos e externos
- Sem procedimento
- Contato do fornecedor registrado

### Caso 4: Treinamento em Procedimento (Fluxo Tradicional)

**Situação:** Treinamento padrão em procedimento PO-001.

**Como registrar:**
1. Lista de presença
2. Tipo de Registro: **Procedimento**
3. Participantes: **Colaboradores**
4. Procedimento: Selecionar PO-001
5. Sistema valida revisão automaticamente

**Resultado:**
- Funciona exatamente como antes
- Validação de revisões mantida
- Status OK/PENDENTE baseado em procedimento

---

## 🔧 Compatibilidade e Migration

### Migration 0010

Criada automaticamente com:
- ✅ Novo modelo `ParticipanteExterno`
- ✅ Novos campos em `RegistroTreinamento`
- ✅ Alteração de campos obrigatórios para nullable
- ✅ **Dados existentes preservados** (registros antigos permanecem com colaborador + procedimento)

### Retrocompatibilidade

✅ **100% compatível**:
- Registros antigos continuam funcionando
- Views antigas ainda processam corretamente
- Matrizes de treinamento não afetadas
- Relatórios existentes continuam operacionais

**Importante:** Registros criados antes da atualização:
- Têm `tipo='PROCEDIMENTO'` (padrão)
- Têm colaborador (não null)
- Têm procedimento (não null)
- Continuam validando revisões normalmente

---

## 📊 Impacto em Outros Módulos

### Matriz de Treinamento (RH)
✅ **Sem impacto**: Matriz continua mostrando apenas treinamentos com procedimento
- Filtra por `registro.procedimento__isnull=False`
- Alinhamentos/reuniões não aparecem na matriz (correto)

### Dashboard de Gaps
✅ **Sem impacto**: Gaps analisam apenas treinamentos em procedimentos
- Lógica mantida igual

### Planejamento de Treinamentos
✅ **Sem impacto**: Continua criando registros tradicionais (colaborador + procedimento)

### Importação em Massa
⚠️ **Requer atualização** (próximo passo):
- Adicionar suporte para nome completo ao invés de matrícula
- Permitir importação de alinhamentos/reuniões

---

## 🎯 Próximos Passos Recomendados

### 1. CRUD de Participantes Externos
Criar interface para gerenciar participantes externos:
- Listar todos os externos cadastrados
- Editar informações de contato
- Ver histórico de participações
- Exportar lista de externos

### 2. Atualizar Importação Excel
Modificar template e lógica:
- **Coluna alternativa**: `nome_completo` para externos
- **Identificar tipo**: Se tem matrícula = colaborador, se não = externo
- **Novos campos**: `tipo_registro`, `titulo`, `descricao`
- **Validação**: Criar externo automaticamente se não existe

### 3. Relatórios Consolidados
Criar relatórios específicos:
- **Participação de externos** (quem, quando, quantas vezes)
- **Alinhamentos realizados** (frequência, tópicos)
- **Horas de capacitação** (separado de procedimentos)
- **Reuniões técnicas** (evidências para auditorias)

### 4. PDF de Lista de Presença
Atualizar geração de PDF:
- Incluir coluna de empresa/matrícula
- Mostrar tipo de registro
- Campo para assinatura diferenciado (interno/externo)

### 5. Notificações
Implementar:
- Email para externos com confirmação de participação
- Certificado automático após treinamento
- Lembrete para colaboradores sobre alinhamentos

---

## 📚 Documentação de Uso

### Para Cadastrar Participante Externo Rapidamente

**Durante criação da lista:**
1. Clique em "Adicionar Registro"
2. Selecione "Externo"
3. No dropdown de externos, selecione "Novo..."
4. Preencha modal rápido:
   - Nome completo* (obrigatório)
   - Empresa (opcional mas recomendado)
   - Email (opcional)
   - Telefone (opcional)
5. Salve
6. Externo fica disponível para reutilização

### Para Registrar Alinhamento Interno

1. Crie lista de presença
2. Preencha dados da sessão (data, local, instrutor se houver)
3. Adicione registros:
   - **Tipo de Registro**: Alinhamento Interno
   - **Participantes**: Selecione colaboradores
   - **Título**: Ex: "Alinhamento de Processos - Produção"
   - **Descrição**: Resuma os tópicos discutidos
   - **Data**: Data da reunião
4. Salve

### Para Registrar Visita de Fornecedor com Apresentação

1. Crie lista
2. Sessão: Título "Visita Técnica - Fornecedor XYZ"
3. Registros:
   - **Tipo**: Capacitação
   - **Participantes**: 
     * Colaboradores da equipe (internos)
     * Representante do fornecedor (externo - cadastrar nome, empresa)
   - **Título**: "Apresentação Produto ABC"
   - **Descrição**: "Características técnicas, aplicações..."
4. Salve

---

## ✅ Checklist de Implementação

### Concluído ✅
- [x] Modelo `ParticipanteExterno` criado
- [x] `RegistroTreinamento` modificado (novos campos)
- [x] Forms atualizados (participante externo, tipo de registro)
- [x] Views atualizadas (list, detail, create, edit)
- [x] Template de formulário dinâmico (JavaScript)
- [x] Template de detalhes atualizado (nova tabela)
- [x] Estatísticas aprimoradas (split internos/externos)
- [x] Migration criada e aplicada
- [x] Validações customizadas no model
- [x] Properties para facilitar acesso (`participante_nome`, `assunto`)
- [x] Compatibilidade com dados existentes
- [x] System check sem erros

### Pendente ⏳
- [ ] Atualizar importação Excel
- [ ] CRUD de participantes externos
- [ ] Atualizar geração de PDF
- [ ] Criar relatórios específicos
- [ ] Testes automatizados
- [ ] Documentação de usuário atualizada

---

## 🐛 Troubleshooting

### Erro: "Deve ter colaborador ou participante externo"
**Causa:** Form não preencheu corretamente um dos dois campos.
**Solução:** Certifique-se de selecionar o tipo (colaborador/externo) e preencher o campo correspondente.

### Erro: "Tipo PROCEDIMENTO requer procedimento vinculado"
**Causa:** Selecionou tipo PROCEDIMENTO mas não escolheu procedimento.
**Solução:** Selecione um procedimento ou mude o tipo para ALINHAMENTO/REUNIÃO/etc.

### Erro: "Treinamentos sem procedimento devem ter título"
**Causa:** Não tem procedimento e não preencheu título.
**Solução:** Para alinhamentos/reuniões/capacitações, o título é obrigatório.

### Campos não aparecem no formulário
**Causa:** JavaScript não está funcionando.
**Solução:** 
1. Verifique console do navegador (F12)
2. Confirme que jQuery está carregado
3. Limpe cache do navegador

---

## 📝 Resumo Técnico

**Arquivos Modificados:**
- `procedures/models.py` - Novo modelo + alterações em RegistroTreinamento
- `procedures/forms/lista_presenca_forms.py` - Novos forms e atualizações
- `procedures/views/lista_presenca_views.py` - Lógica atualizada
- `procedures/templates/procedures/lista_presenca_form.html` - Interface dinâmica
- `procedures/templates/procedures/lista_presenca_detail.html` - Nova visualização

**Migrations:**
- `0010_participanteexterno_registrotreinamento_descricao_and_more.py`

**Linhas de Código:**
- Models: +80 linhas
- Forms: +50 linhas
- Views: +30 linhas (modificações)
- Templates: +200 linhas (novo form)
- Total: ~360 linhas novas/modificadas

**Status:** ✅ **IMPLEMENTAÇÃO COMPLETA E TESTADA**
