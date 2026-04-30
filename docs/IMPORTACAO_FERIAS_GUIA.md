# 📥 Importação em Massa de Férias

## Visão Geral

Funcionalidade que permite importar férias de múltiplos colaboradores a partir de um arquivo CSV ou Excel, economizando tempo em operações em massa.

## Acesso

**URL:** `/rh/gestao-ferias/`
**Botão:** Azul com ícone 📥 "Importar" (ao lado dos botões "Registrar Férias" e "Atualizar Status")

## Fluxo de Uso

### 1. Aceder à Página de Importação
```
Gestão de Férias → Botão "Importar"
```

### 2. Selecionar Arquivo
- **Opção A:** Clicar na zona de upload
- **Opção B:** Arrastar arquivo para a zona

### 3. Confirmação
- Clique em "Importar Férias"
- Você verá mensagem com resultado:
  ```
  ✅ Importação concluída! X criados, Y atualizados, Z erros
  ```

## Formato do Arquivo

### Colunas Obrigatórias

| Coluna | Descrição | Formato | Exemplo |
|--------|-----------|---------|---------|
| **Matrícula** | ID único do colaborador | Texto/Número | `23`, `339` |
| **Data Início** | Primeiro dia de férias | DD/MM/YYYY | `01/01/2026` |
| **Data Fim** | Último dia de férias | DD/MM/YYYY | `31/01/2026` |

### Colunas Opcionais

| Coluna | Descrição | Padrão | Valores Aceitos |
|--------|-----------|--------|-----------------|
| **Dias Solicitados** | Quantidade de dias | Auto-calculado | Número inteiro |
| **Aprovada** | Status de aprovação | Não | Sim/Não, True/False, 1/0 |
| **Descrição** | Observações | Vazio | Texto livre |

### Exemplo de Arquivo CSV

```csv
Matrícula,Data Início,Data Fim,Dias Solicitados,Aprovada,Descrição
23,01/01/2026,31/01/2026,30,Sim,Férias planejadas
339,29/12/2025,27/01/2026,30,Sim,
223,29/12/2025,07/01/2026,10,Não,Aguardando aprovação
```

### Exemplo de Arquivo Excel

Mesma estrutura que CSV, mas em formato `.xlsx` ou `.xls`

## Funcionalidades

### ✅ Download de Templates
Página oferece botões para baixar templates de exemplo:
- **Template CSV** - Formato simplificado, abrir em qualquer editor
- **Template Excel** - Formato profissional, abrir em Excel/Calc

### ✅ Validação Inteligente
- Detecta automaticamente CSV ou Excel
- Normaliza espaços em branco em nomes de coluna
- Converte datas em múltiplos formatos
- Valida matrícula do colaborador

### ✅ Processamento Robusto
- **Criar**: Se combinação (colaborador + datas) não existe, cria registro
- **Atualizar**: Se registro já existe, atualiza com novos dados
- **Erro Tolerante**: Continua processando mesmo se alguma linha falhar
- **Feedback Detalhado**: Mostra até 5 primeiros erros

### ✅ Segurança
- Verificação de permissão (usuário deve ser RH/DP/QUALIDADE/staff/superuser)
- CSRF token incluído no formulário
- Autenticação obrigatória
- Logs detalhados de todas as operações

## Permissões

Apenas usuários com acesso RH podem usar esta funcionalidade:
- ✅ Superuser
- ✅ Staff
- ✅ Usuários no setor "RH"
- ✅ Usuários no setor "DP" (Departamento Pessoal)
- ✅ Usuários no setor "QUALIDADE"

Tentativa de acesso sem permissão redireciona para gestão de férias com mensagem de erro.

## Cenários de Uso

### Cenário 1: Férias Planejadas Anuais
```
Arquivo: ferias_2026.csv
Conteúdo: 30 colaboradores com férias agendadas
Resultado: 30 registros criados com status "PLANEJADO" (aprovada=False)
```

### Cenário 2: Férias Aprovadas
```
Arquivo: ferias_janeiro_aprovadas.xlsx
Conteúdo: 10 colaboradores com férias já aprovadas
Resultado: 10 registros criados com status "PLANEJADO" (aprovada=True)
```

### Cenário 3: Atualização de Dados
```
Arquivo: ferias_atualizar.csv
Conteúdo: 3 registros de férias já existentes com dias diferentes
Resultado: 3 registros atualizados com novo número de dias
```

## Mensagens de Resultado

### ✅ Sucesso Completo
```
✅ Importação concluída! 25 criados, 5 atualizados
```

### ⚠️ Sucesso Parcial
```
⚠️ Importação concluída! 20 criados, 3 atualizados, 2 erros

Detalhes dos erros:
- Linha 15: Colaborador com matrícula '999' não encontrado
- Linha 22: Erro ao converter datas - time data did not match format
```

### ❌ Erro
```
❌ Erro na importação: [descrição do erro]
```

## Tratamento de Erros

### Erro: "Matrícula obrigatória"
Certifique-se de que:
- Coluna "Matrícula" existe no arquivo
- Nenhuma linha tem matrícula em branco
- Nomes de coluna correspondem exatamente

### Erro: "Data Início e Data Fim são obrigatórios"
Certifique-se de que:
- Coluna "Data Início" existe
- Coluna "Data Fim" existe
- Datas estão no formato `DD/MM/YYYY`
- Sem linhas em branco

### Erro: "Colaborador não encontrado"
- Verifique se a matrícula existe no sistema
- A matrícula deve ser exatamente a mesma (sensitive)
- Você pode visualizar matrículas na página de gestão de férias

### Erro: "Erro ao converter datas"
- Confirme formato: `DD/MM/YYYY`
- Não use formatos alternativos (YYYY-MM-DD, MM/DD/YYYY, etc)
- Datas devem ser válidas (não dia 30 de fevereiro, por exemplo)

## API e Integração

### Método POST
```
POST /rh/gestao-ferias/importar/
Content-Type: multipart/form-data

Form Data:
- arquivo_importacao: <file>
- csrf_token: <token>
```

### Resposta
- ✅ Sucesso: Redireciona para `/rh/gestao-ferias/` com mensagens de sucesso
- ❌ Erro: Redireciona para `/rh/gestao-ferias/importar/` com mensagem de erro

## Logs

Todas as operações são registradas em:
```
logs/django.log
```

Exemplo de log:
```
2026-01-08 20:00:00 - INFO - 🔄 Iniciando importação de férias do arquivo: ferias.csv
2026-01-08 20:00:00 - INFO - 📊 Arquivo contém 30 linhas
2026-01-08 20:00:01 - INFO - ✅ Férias criadas: AUGUSTO CEZAR DA ROCHA BOMFIM (01/01/2026 a 31/01/2026)
2026-01-08 20:00:02 - INFO - 📊 Importação finalizada: 25 criados, 5 atualizados, 0 erros
```

## Limitações Atuais

- ⚠️ Arquivo máximo: ~10MB (limite padrão Django)
- ⚠️ Processamento é síncrono (pode ser lento para >1000 registros)
- ⚠️ Não detecta duplicatas dentro do mesmo arquivo

## Futuras Melhorias

- [ ] Async task para importações grandes
- [ ] Preview dos dados antes de confirmar
- [ ] Validação de conflitos de férias (datas sobrepostas)
- [ ] Template com suporte a mais campos (vencimento, motivo, etc)
- [ ] Integração com API de folha de ponto

## Compatibilidade

| Navegador | Status | Notas |
|-----------|--------|-------|
| Chrome | ✅ | Completo |
| Firefox | ✅ | Completo |
| Safari | ✅ | Completo |
| Edge | ✅ | Completo |
| IE 11 | ❌ | Não suportado |

| Formato | Status | Notas |
|---------|--------|-------|
| CSV | ✅ | Recomendado |
| XLSX | ✅ | Office 2007+ |
| XLS | ✅ | Office 97-2003 |

## Atalho

Você pode acessar diretamente via URL:
```
https://seu-dominio.com/rh/gestao-ferias/importar/
```

---

**Versão:** 1.0
**Data de Criação:** 08/01/2026
**Última Atualização:** 08/01/2026
