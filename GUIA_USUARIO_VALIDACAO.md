# 🎯 Guia Completo - Sistema de Validação de Matriz de Habilidades

## 📖 Índice
1. [Visão Geral](#visão-geral)
2. [Para Solicitante](#para-solicitante)
3. [Para Validador](#para-validador)
4. [Dashboard e Relatórios](#dashboard-e-relatórios)
5. [FAQs](#faqs)
6. [Informações Técnicas](#informações-técnicas)

---

## 🎬 Visão Geral

O **Sistema de Validação de Matriz** permite que colaboradores solicitem validação formal de matrizes de habilidades para líderes ou supervisores. Isso garante:

✅ Auditoria completa de quem validou o quê e quando  
✅ Rastreabilidade de todas as avaliações  
✅ Aprovação formal antes de usar em decisões de RH  
✅ Histórico permanente de validações  

### **Fluxo Básico**

```
SOLICITANTE                 SISTEMA                    VALIDADOR
    │                          │                           │
    ├─ Clica "Solicitar" ─────>│                           │
    │                          ├─ Cria Solicitação        │
    │                          ├─ Status: PENDENTE         │
    │                          ├─ Notifica ───────────────>│
    │                          │                           │
    │                          │<─ Validador revisa ─────┤
    │                          │                           │
    │                          │<─ Aprova ou Rejeita ────┤
    │                          │                           │
    │<─ Registra no Histórico ─┤                           │
    │  (HistoricoValidacaoMassa)                           │
    │
```

---

## 👤 Para Solicitante

### **Passo 1: Acessar Avaliações**
```
Menu → Procedimentos → Avaliações
```

### **Passo 2: Selecionar Matriz**
- Escolha uma **Matriz de Habilidades**
- Sistema mostra todos os colaboradores × disciplinas

### **Passo 3: Clicar em "Solicitar Validação"**
Botão localizado no topo direito da tabela

### **Passo 4: Preencher Formulário**
```
┌─────────────────────────────────────┐
│ Solicitar Validação                 │
├─────────────────────────────────────┤
│                                     │
│ Selecione o Validador *             │
│ [DROPDOWN com líderes/supervisores] │
│                                     │
│ Motivo (Opcional)                   │
│ [TEXTAREA]                          │
│ Ex: "Preciso para avaliação de      │
│      desempenho do 2º semestre"    │
│                                     │
│ Resumo:                             │
│ - 8 Colaboradores                   │
│ - 5 Disciplinas                     │
│                                     │
│ [Cancelar] [Enviar Solicitação]     │
└─────────────────────────────────────┘
```

### **Passo 5: Confirmação**
Mensagem de sucesso aparece:
```
✅ "Solicitação de validação enviada para JOÃO SILVA!"
```

---

## 🔐 Para Validador (Líder/Supervisor)

### **Passo 1: Acessar Pendências**
```
Menu → Procedimentos → Validações → Pendências
```

### **Passo 2: Ver Matriz a Validar**
Tabela com:
- **Matriz**: Nome da matriz
- **Solicitante**: Quem pediu
- **Data**: Quando foi pedido
- **Motivo**: Por que precisa validar
- **Ação**: Botão "Validar"

Exemplo:
```
┌───────────────┬─────────────────┬───────────┬──────────────────┐
│ Matriz        │ Solicitante     │ Data      │ Ação             │
├───────────────┼─────────────────┼───────────┼──────────────────┤
│ Surfaçagem    │ MARIA SANTOS    │ 29/12     │ [Validar]        │
│ Qualidade     │ JOÃO COSTA      │ 28/12     │ [Validar]        │
└───────────────┴─────────────────┴───────────┴──────────────────┘
```

### **Passo 3: Clicar em "Validar"**
Sistema mostra:
- Quem solicitou e quando
- Motivo da solicitação
- **Resumo de Avaliações**:
  - Total de avaliações
  - Colaboradores
  - Disciplinas

### **Passo 4: Revisar Avaliações**
Todas as avaliações são exibidas agrupadas por colaborador:

```
ANDREA SANTOS - 2 Avaliações
├─ Preparação: [2] (Treinado) - por João Silva em 15/12
└─ Fitagem: [1] (Em Treinamento) - por João Silva em 15/12

ANTONIO DIAS - 3 Avaliações
├─ Preparação: [2] (Treinado) - por Maria José em 20/12
├─ Fitagem: [3] (LOFT) - por Maria José em 20/12
└─ Inspeção: [+] (Não Avaliado)
```

### **Passo 5: Tomar Decisão**
Escolher uma opção:

```
⭕ Validar
   └─ Aprovar todas as avaliações
      └─ Cria registro em HistoricoValidacaoMassa
      └─ Status muda para "validada"

⭕ Rejeitar
   └─ Solicitar revisão
   └─ Status muda para "rejeitada"
   └─ Pode ser reenviada depois
```

### **Passo 6: Adicionar Comentário**
```
[TEXTAREA] Comentário
Ex: "Avaliações revisadas. Aprovadas para uso em 
     avaliação de desempenho."
```

### **Passo 7: Processar**
Clica em "Processar Validação"

**Resultado**:
```
✅ "Matriz Surfaçagem validada com sucesso!"
   Histórico registrado:
   - Validador: JOÃO SILVA
   - 6 avaliações validadas
   - Timestamp automático
```

---

## ⚡ Validação Rápida (Sem Solicitação)

Para casos onde há poucas mudanças:

### **Acesso Rápido**
```
Menu → Procedimentos → Avaliações
Selecione uma matriz
Clique em "Validar Rápido"
```

### **Fluxo**
```
1. Sistema mostra total de avaliações
2. Você confirma
3. Cria automaticamente HistoricoValidacaoMassa
4. Sem necessidade de solicitação prévia
```

### **Quando Usar**
- ✅ Validação simples
- ✅ Poucas avaliações
- ✅ Sem mudanças significativas
- ✅ Validação informal/rápida

---

## 📊 Dashboard e Relatórios

### **Ver Pendências**
```
/procedures/validacoes/pendentes/
```
- Lista todas as matrizes esperando você validar
- Filtro por data
- Mostra prioridades

### **Histórico Completo**
```
No admin: procedures → SolicitacaoValidacaoMatriz
No admin: procedures → HistoricoValidacaoMassa
```

Dados registrados:
- Quem solicitou
- Quem validou
- Quando foi feito
- Status (pendente/validada/rejeitada)
- Motivos (solicitação e rejeição)
- Timestamp exato

---

## ❓ FAQs

### **P: Posso validar uma matriz que não foi solicitada?**
R: Sim! Use "Validar Rápido" para validações informais.

### **P: E se eu rejeitar a matriz?**
R: Ela voltará ao solicitante com status "rejeitada". Ele pode revisá-la e reenviar.

### **P: Quem pode ver o histórico?**
R: Apenas admin no Django. Pessoal do RH pode ver relatórios.

### **P: Preciso assinar digitalmente?**
R: Não (por enquanto). O sistema registra automaticamente quem validou.

### **P: Quanto tempo leva para registrar?**
R: Instantâneo! Timestamp automático no momento da validação.

### **P: Posso validar múltiplas matrizes de uma vez?**
R: Não ainda, mas pode fazer rápido usando "Validar Rápido".

### **P: E se eu clicar errado?**
R: Cada validação cria um registro permanente. Para desfazer, contate o administrador.

---

## 🔧 Informações Técnicas

### **Modelos de Dados**

#### **SolicitacaoValidacaoMatriz**
Rastreia solicitações de validação

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `matriz` | FK | Qual matriz será validada |
| `solicitante` | FK | Quem pediu |
| `validador` | FK | Quem vai validar |
| `status` | Char | pendente/validada/rejeitada |
| `motivo_solicitacao` | Text | Por que pedir |
| `motivo_rejeicao` | Text | Se rejeitar, por quê |
| `criado_em` | DateTime | Quando foi criado |
| `validado_em` | DateTime | Quando foi validado |

#### **HistoricoValidacaoMassa**
Registra execução de validações

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `matriz` | FK | Qual matriz foi validada |
| `validador` | FK | Quem validou |
| `total_avaliacoes` | Int | Quantas avaliações existiam |
| `avaliacoes_atualizadas` | Int | Quantas foram aprovadas |
| `motivo` | Text | Comentário do validador |
| `executado_em` | DateTime | Timestamp exato |

### **URLs Disponíveis**

| Função | URL | Usuários |
|--------|-----|----------|
| Solicitar | `/matrizes/{id}/solicitar-validacao/` | Todos |
| Validar | `/validacoes/{id}/validar/` | Validador |
| Rápido | `/matrizes/{id}/validacao-rapida/` | Todos |
| Pendências | `/validacoes/pendentes/` | Validador |

### **Permissões**

```python
- Qualquer usuário: Pode solicitar validação
- Validador designado: Pode validar
- Admin: Pode ver tudo + editar histórico
```

---

## 📱 Interface Mobile

O sistema é responsivo e funciona bem em:
- ✅ Desktop (recomendado)
- ✅ Tablet
- ✅ Mobile (com scroll horizontal na tabela)

---

## 🚨 Erros Comuns

### ❌ "Você não tem permissão para validar"
- Você não é o validador designado
- Contate o administrador

### ❌ "Colaborador não encontrado"
- Matriz não tem colaboradores associados
- Vá para editar matriz e adicione colaboradores

### ❌ "Validação já existe"
- Matriz foi validada antes
- Procure no histórico

---

## 💡 Dicas Úteis

1. **Validação em Lote**: Use "Validar Rápido" para múltiplas matrizes simples
2. **Comentário Descritivo**: Deixe sempre um comentário explicando sua decisão
3. **Backup**: O sistema registra tudo automaticamente (não precisa salvar)
4. **Auditoria**: Todos os dados ficam permanentes no banco
5. **Notificações**: Peça ao admin para ativar notificações por email

---

## 📞 Suporte

Se tiver problemas:

1. Verifique se está logado como validador designado
2. Verifique se a matriz tem colaboradores e disciplinas
3. Verifique o histórico em django admin
4. Procure logs de erro em console

---

## ✅ Checklist de Configuração

```
☐ Modelos criados (SolicitacaoValidacaoMatriz, HistoricoValidacaoMassa)
☐ Migrations aplicadas (0017_...)
☐ Views criadas (validacao_views.py)
☐ Templates criados (4 arquivos HTML)
☐ URLs configuradas (procedures/urls.py)
☐ Botões adicionados na matriz (solicitar, rápido, pendências)
☐ Dados de teste criados (test_validacao_sistema.py)
☐ Servidor rodando (localhost:8000)
☐ Acessar: /procedures/avaliacoes/
```

---

**Última atualização**: 29/12/2025  
**Status**: ✅ PRONTO PARA PRODUÇÃO  
**Suporte**: Consulte o arquivo `VALIDACAO_MATRIZ_IMPLEMENTACAO.md`
