# Guia de Migração: Railway para Vercel + Appwrite

Este guia orienta passo a passo a migração da infraestrutura do CalibraQMS do Railway para a plataforma **Vercel** (para a aplicação Django) combinada com o **Appwrite** (banco de dados do módulo de Ações).

---

## 📋 Arquitetura de Produção Proposta

1. **Vercel (Serverless):** Hospeda o servidor web Django (através de Serverless Functions baseadas em Python 3.12).
2. **PostgreSQL Relacional (Neon ou Supabase):** Banco de dados principal para o Django ORM (módulos como `rh`, `metrologia`, `users`, tabelas de sistema do Django).
3. **Appwrite Database:** Utilizado especificamente pelo módulo `acoes` para ler os registros migrados.
4. **Armazenamento de Mídia (AWS S3 ou Cloudflare R2):** Hospeda os arquivos enviados pelos usuários (como PDFs de certificados) de forma permanente, configurado no `settings.py` via `django-storages`.

---

## 🛠️ Passo 1: Configurar o Banco Relacional Principal (PostgreSQL)

Como o Vercel executa funções efêmeras, não é possível utilizar o banco SQLite local (`db.sqlite3`) para produção.

1. Crie uma conta gratuita em um provedor de PostgreSQL gerenciado, como **[Neon](https://neon.tech/)** ou **[Supabase](https://supabase.com/)**.
2. Crie um novo banco de dados no painel e copie a URL de conexão (Connection String), que possui o formato:
   `postgres://usuario:senha@host-do-banco:5432/nomedobanco?sslmode=require`
3. Salve essa URL para configurar a variável `DATABASE_URL` no Vercel.

---

## 🛡️ Passo 2: Configurar o Projeto no Appwrite

Para o funcionamento do módulo de `acoes`, você precisa configurar a base de dados e a coleção correspondente no Appwrite.

### 1. Criar o Projeto e Banco
1. Acesse o **[Console do Appwrite](https://cloud.appwrite.io)**.
2. Crie um novo projeto chamado `CalibraWeb` (ou use um existente) e anote o **Project ID**.
3. Vá em **Databases** e crie uma nova base de dados. Anote o **Database ID** (se criado com o ID padrão, será `default`).

### 2. Criar a Coleção e Atributos (Automatizado)
Você pode optar por criar a coleção e seus 18 atributos manualmente ou usar o script de automação fornecido `setup_appwrite_schema.py` no diretório raiz do projeto:

```bash
# Defina as variáveis de ambiente locais no seu terminal
set APPWRITE_ENDPOINT="https://cloud.appwrite.io/v1"
set APPWRITE_PROJECT="seu_project_id"
set APPWRITE_API_KEY="sua_api_key"
set APPWRITE_DATABASE_ID="default"

# Execute o script de setup automático
python setup_appwrite_schema.py
```
*Este script verificará/criará o banco de dados, a coleção `acoes` e criará todos os atributos com os tipos corretos de forma totalmente assíncrona.*

Caso prefira configurar manualmente, crie a coleção com ID `acoes` e adicione estes atributos na aba **Attributes**:

| Nome do Atributo | Tipo no Appwrite | Tamanho/Configuração | Requerido | Observações |
| :--- | :--- | :--- | :---: | :--- |
| `numero_registro` | String | 100 | Não | Código de registro (ex: AC-2026-001) |
| `ano` | Integer | - | Não | Ano do registro |
| `unidade` | String | 100 | Não | Unidade administrativa |
| `titulo` | String | 255 | Sim | Título da ação corretiva |
| `descricao` | String | 5000 | Sim | Detalhamento do problema |
| `tipo` | String | 50 | Sim | choices: `corretiva` ou `preventiva` |
| `tipo_solucao` | String | 100 | Não | Categoria da solução |
| `prioridade` | String | 50 | Sim | choices: `baixa`, `media`, `alta`, `critica` |
| `origem` | String | 255 | Não | Origem do problema |
| `causa_raiz` | String | 5000 | Não | Análise de causa raiz |
| `status` | String | 50 | Sim | choices: `aberta`, `em_progresso`, `concluida`, `cancelada` |
| `data_abertura` | String | 50 | Não | Data no formato YYYY-MM-DD |
| `data_vencimento` | String | 50 | Sim | Prazo final programado (YYYY-MM-DD) |
| `data_conclusao` | String | 50 | Não | Data em que foi concluída (YYYY-MM-DD) |
| `criado_por` | String | 255 | Não | Nome ou identificação do criador |
| `responsavel` | String | 255 | Não | Nome ou identificação do responsável |
| `acoes_status_resumo` | String | 255 | Não | Campo resumo auxiliar (usado no frontend) |

4. Vá na aba **Settings** da coleção `acoes` e defina as **Permissions** (Permissões):
   - Adicione a role `Any` (ou usuários autenticados) com permissão para **Read**.
   - Para segurança de escrita, a gravação de dados pode ser restrita ou atribuída via API Key.

### 3. Criar uma API Key do Appwrite
1. No menu lateral do console do Appwrite, vá em **Overview** -> **Integrations** -> **API Keys**.
2. Clique em **Create API Key**.
3. Dê o nome de `CalibraWeb Backend`.
4. Defina as seguintes **scopes (permissões)** de acesso:
   - `databases.read`
   - `databases.write`
   - `documents.read`
   - `documents.write`
5. Salve e copie a chave secreta gerada. Esta será a sua `APPWRITE_API_KEY`.

---

## 🚀 Passo 3: Configurar e Implantar no Vercel

### 1. Importar o Repositório no Vercel
1. Conecte sua conta do GitHub ao Vercel e importe o projeto `CalibraQMS`.
2. O Vercel detectará as configurações baseadas no arquivo `vercel.json` automaticamente.

### 2. Configurar Variáveis de Ambiente no Vercel
Nas configurações do seu projeto no Vercel (**Settings** -> **Environment Variables**), adicione as seguintes chaves:

| Variável | Valor Recomendado | Finalidade |
| :--- | :--- | :--- |
| `DEBUG` | `False` | Desativa o modo de depuração para segurança em produção |
| `SECRET_KEY` | *Gerar chave aleatória longa* | Chave de criptografia secreta do Django |
| `DATABASE_URL` | *Connection string obtida no Passo 1* | Conexão com o PostgreSQL (Neon/Supabase) |
| `APPWRITE_ENDPOINT` | `https://cloud.appwrite.io/v1` | Endpoint da API do Appwrite |
| `APPWRITE_PROJECT` | *Project ID obtido no Passo 2* | ID do projeto no Appwrite |
| `APPWRITE_API_KEY` | *API Key gerada no Passo 2* | Token de escrita/leitura no Appwrite |
| `APPWRITE_DATABASE_ID` | *Database ID do Passo 2* | ID do banco de dados do Appwrite |
| `CRON_SECRET` | *Gerar chave aleatória forte* | Token para autenticação segura do Vercel Cron |
| `VERCEL` | `1` | Habilita a detecção dinâmica de ambiente no `settings.py` |

---

## 📦 Passo 4: Executar a Migração e Importar Dados Existentes

### 1. Migração do Schema Relacional (PostgreSQL)
A primeira implantação no Vercel executará as migrações automaticamente no PostgreSQL através do script `build_files.sh`. 
Se desejar aplicar manualmente a partir da sua máquina local apontando para o novo banco de dados de produção:
```bash
# No terminal local (substitua a DATABASE_URL pela de produção temporariamente)
set DATABASE_URL="postgres://..."
python manage.py migrate --noinput
python manage.py setup_module_permissions
python manage.py ensure_superuser
```

### 2. Importação dos Dados de Ações para o Appwrite (Recomendado)
Para carregar os registros de ações anteriores que estavam no banco de dados local do Django para o Appwrite de forma idempotente e segura (resolvendo os nomes completos dos responsáveis a partir das chaves estrangeiras):

1. Defina as variáveis de ambiente locais do Appwrite no seu terminal (as mesmas do Passo 2).
2. Execute o comando de gerenciamento customizado do Django:
   ```bash
   python manage.py import_to_appwrite
   ```
   *Nota: Este comando lerá os registros diretamente do banco de dados configurado no Django (ex: sqlite local ou postgres), converterá os colaboradores (chaves estrangeiras) em nomes reais legíveis, criará IDs idempotentes (`django_<id>`) no Appwrite e atualizará ou criará os documentos na coleção `acoes` sem duplicar registros caso executado múltiplas vezes.*

---

## ⏰ Passo 5: Configurar Cron Jobs no Vercel

O Vercel executa tarefas agendadas chamando rotas HTTP de forma serverless. Já deixamos configurado no arquivo `vercel.json` o seguinte agendamento:

```json
"crons": [
  {
    "path": "/api/cron/run-tasks/",
    "schedule": "*/15 * * * *"
  }
]
```

Isso fará com que o Vercel invoque o endpoint `/api/cron/run-tasks/` a cada 15 minutos.
* **Segurança:** O Vercel envia automaticamente o header `Authorization: Bearer <CRON_SECRET>` na requisição. Nossa implementação no Django valida esse header contra a variável de ambiente `CRON_SECRET` do projeto, impedindo acessos externos não autorizados ao gatilho de tarefas.
* **Tarefas Executadas:** A view de cron executará a atualização das datas de vencimento de ações e a sincronização do status de férias dos colaboradores de forma síncrona e rápida.
