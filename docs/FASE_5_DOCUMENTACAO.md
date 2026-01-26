# FASE 5 - SISTEMA DE EXPORT E RELATÓRIOS AGENDADOS

## 📋 Visão Geral

A Fase 5 implementa um sistema robusto de exportação de dados (Excel, CSV, PDF) e relatórios automáticos via Celery, permitindo que usuários compartilhem dados de calibração e recebam alertas periódicos sobre instrumentos vencidos.

## 🎯 Objetivos Alcançados

### 1. ✅ Sistema de Exportação Multi-Formato
- **Excel**: Formatação profissional com cabeçalhos, estilos, resumos
- **CSV**: UTF-8, compatível com imports de banco de dados
- **PDF**: Com tabelas, títulos, formatação reportlab

### 2. ✅ Três Novos Pontos de Exportação
1. **Exportar Instrumentos** - Lista com filtros preservados
2. **Exportar Estatísticas** - Dashboard com KPIs
3. **Relatório de Vencidos** - Instrumentos com calibração expirada

### 3. ✅ Preservação de Filtros
- Query strings encaminhadas nas URLs de export
- Mesmo filtros da listagem são aplicados na exportação
- Usuário pode exportar dados filtrados sem perder contexto

### 4. ✅ Relatórios Automáticos Agendados
- **Diário (8h)**: Instrumentos vencidos em Excel
- **Semanal (2ª 9h)**: Estatísticas completas
- **Crítico (4/4h)**: Alertas de instrumentos expirados por email

## 📁 Arquivos Criados/Modificados

### Novos Arquivos
```
metrologia/exportadores.py          (370+ linhas)
  ├─ ExportadorInstrumentos (Excel, CSV, PDF)
  └─ ExportadorEstatisticas (Excel, PDF)

qms/tests_fase5.py                  (270+ linhas)
  ├─ ExportadorInstrumentosTest (4 casos)
  ├─ ExportadorEstatisticasTest (3 casos)
  └─ ExportViewsTest (6 casos)

qms/celery_beat_config.py           (Configuração Beat)
  ├─ Agendamento diário (8h)
  ├─ Agendamento semanal (2ª 9h)
  └─ Agendamento crítico (a cada 4h)

CONFIGURACAO_EMAIL_FASE5.md         (Guia de setup email)
```

### Modificados
```
qms/views.py                         (+150 linhas)
  ├─ exportar_instrumentos_view() - Linha 1189
  ├─ exportar_estatisticas_view() - Linha 1265
  └─ relatorio_vencidos_view() - Linha 1339

qms/urls.py                          (+3 rotas)
  ├─ metrologia/instrumentos/exportar/
  ├─ metrologia/estatisticas/exportar/
  └─ metrologia/vencidos/

qms/tasks.py                         (+180 linhas)
  ├─ gerar_relatorio_diario_vencidos
  ├─ gerar_relatorio_semanal_estatisticas
  └─ gerar_relatorio_alerta_critico

templates/
  ├─ instrumentos_lista.html         (Botão export)
  └─ estatisticas_calibracao.html    (Botão export)
```

## 🔧 Arquitetura

### 1. Módulo de Exportação (metrologia/exportadores.py)

```python
ExportadorInstrumentos
├─ exportar_excel(queryset, response)
├─ exportar_csv(queryset, response)
├─ exportar_pdf(queryset, response)
└─ _get_status_text(instrumento)

ExportadorEstatisticas
├─ exportar_excel(response, kpis, categorias, setores)
├─ exportar_pdf(response, kpis, categorias, setores)
├─ _preench_kpis_excel(sheet, kpis)
├─ _preench_categoria_excel(sheet, categorias)
└─ _preench_setor_excel(sheet, setores)
```

### 2. Views de Exportação

**exportar_instrumentos_view()**
- Aplica mesmos filtros da listagem
- Suporta: ?formato=excel|csv|pdf
- Mantém todos query parameters
- Exemplo: `?status=vencido&setor=TI&formato=excel`

**exportar_estatisticas_view()**
- Recalcula KPIs em tempo real
- Formatos: Excel (multi-sheet) ou PDF
- Inclui: totais, categorias, setores

**relatorio_vencidos_view()**
- Filtra apenas: ativo=True, data_proxima_calibracao < hoje
- Ordena por: data_proxima_calibracao (urgentes primeiro)
- Formatos: Excel (default) ou PDF

### 3. Celery Scheduled Tasks

**gerar_relatorio_diario_vencidos**
```
Agendamento: 8h diariamente
Ação: Email com Excel anexado
Destinatários: REPORT_EMAIL_TO
Conteúdo: Todos instrumentos vencidos do dia
```

**gerar_relatorio_semanal_estatisticas**
```
Agendamento: 2ª-feira 9h
Ação: Email com Excel multi-sheet
Destinatários: REPORT_EMAIL_TO
Conteúdo: KPIs, por categoria, por setor
```

**gerar_relatorio_alerta_critico**
```
Agendamento: A cada 4 horas
Ação: Email de alerta (se houver vencidos)
Destinatários: ALERT_EMAIL_TO
Conteúdo: Lista de instrumentos com dias vencidos
```

## 📊 Formatos de Saída

### Excel
- **Header**: Estilos, cores, fontes
- **Dados**: Formatação condicional
- **Resumo**: Estatísticas ao final
- **Validação**: Dados UTF-8 compatíveis

### CSV
- **Encoding**: UTF-8 (compatível com UTF-16 do Excel)
- **Delimitador**: Vírgula
- **Quoting**: Apenas quando necessário
- **Headers**: Inclusos

### PDF
- **Tabelas**: ReportLab com linhas/borders
- **Paginação**: Automática
- **Cabeçalho**: Logo/título em cada página
- **Resumo**: Totalizações ao final

## 🚀 Como Usar

### 1. Exportar Instrumentos (UI)
```
1. Ir para: Dashboard → Metrologia → Instrumentos
2. Aplicar filtros desejados (status, setor, etc)
3. Clicar botão "Exportar"
4. Escolher formato: Excel, CSV ou PDF
```

### 2. Exportar via URL
```
GET /metrologia/instrumentos/exportar/?status=vencido&formato=excel
GET /metrologia/estatisticas/exportar/?formato=pdf
GET /metrologia/vencidos/?formato=excel
```

### 3. Executar Tarefas Manualmente
```bash
# Terminal
celery -A config call qms.tasks.gerar_relatorio_diario_vencidos

# Django Shell
python manage.py shell
>>> from qms.tasks import gerar_relatorio_diario_vencidos
>>> gerar_relatorio_diario_vencidos.delay()
```

## ⚙️ Configuração Necessária

### 1. Email Backend (settings.py)
Veja `CONFIGURACAO_EMAIL_FASE5.md` para opções:
- Gmail (recomendado)
- SendGrid
- AWS SES
- Local (console, para teste)

### 2. Celery Beat (celery_beat_config.py)
Importar no seu `config/celery.py`:
```python
from qms.celery_beat_config import CELERY_BEAT_SCHEDULE
app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
```

### 3. Variáveis de Ambiente
```bash
# .env
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=app-password-16-chars
REPORT_EMAIL_TO=gestor@empresa.com,supervisor@empresa.com
ALERT_EMAIL_TO=gestor@empresa.com
```

## 🧪 Testes

### Executar Testes de Fase 5
```bash
python manage.py test qms.tests_fase5 -v 2
```

### Casos de Teste
- **ExportadorInstrumentosTest** (4):
  - Inicialização
  - Geração Excel
  - Geração CSV
  - Geração PDF
  - Status text (vencido/vigente)

- **ExportadorEstatisticasTest** (3):
  - Inicialização
  - Geração Excel
  - Geração PDF

- **ExportViewsTest** (6):
  - Exportar instrumentos (Excel)
  - Exportar instrumentos (CSV)
  - Exportar com filtros
  - Exportar estatísticas (Excel)
  - Relatório vencidos
  - Autenticação requerida

### Teste Manual de Email
```bash
# Terminal 1: Flower (monitor)
celery -A config flower

# Terminal 2: Worker
celery -A config worker -l info

# Terminal 3: Beat
celery -A config beat -l info

# Terminal 4: Dispara tarefa
python manage.py shell
>>> from qms.tasks import gerar_relatorio_alerta_critico
>>> gerar_relatorio_alerta_critico.delay()
```

## 📈 Próximas Melhorias (Fase 6+)

- [ ] Agendamento customizável via admin
- [ ] Template de email em HTML
- [ ] Gráficos nos PDFs
- [ ] Exportação em tempo real (streaming)
- [ ] API de exportação com autenticação token
- [ ] Histórico de exports (auditoria)
- [ ] Webhook para integrações externas
- [ ] Exportação em múltiplos formatos simultâneos

## 📚 Dependências Necessárias

```
openpyxl>=3.0.0          # Excel
reportlab>=4.0.0         # PDF
celery>=5.3.0            # Task queue
```

Adicionar ao `requirements.txt` se não estiverem:
```bash
pip install openpyxl reportlab celery
```

## 🔍 Troubleshooting

### Email não enviando
- ✓ Verificar credenciais em settings.py
- ✓ Testar com console backend primeiro
- ✓ Ver logs do worker: `celery -A config worker -l debug`
- ✓ Verificar firewall SMTP (porta 587)

### Arquivo corrompido no export
- ✓ Verificar encoding dos dados (UTF-8)
- ✓ Validar caracteres especiais
- ✓ Usar `codecs.open()` se necessário

### Tarefa não rodando
- ✓ Verificar Beat scheduler rodando
- ✓ Ver logs: `celery -A config beat -l debug`
- ✓ Verificar CELERY_BEAT_SCHEDULE em config/celery.py

## 📝 Commits Realizados

```
d8f4635 - feat: Implement comprehensive export functionality (Phase 5)
         Files: +1055 insertions
         - metrologia/exportadores.py (370+ lines)
         - qms/tests_fase5.py (270+ lines)
         - qms/views.py (+150 lines)
         - qms/urls.py (+3 routes)
         - qms/tasks.py (+180 lines)
         - 2 templates (export buttons)
```

## ✅ Status Final

- ✅ Exportação Excel, CSV, PDF implementada
- ✅ Preservação de filtros funcionando
- ✅ 13 testes unitários criados
- ✅ 3 tarefas Celery agendadas
- ✅ Documentação completa
- ⚠️ Email backend: Aguardando configuração
- ⚠️ Celery Beat: Aguardando integração com config/celery.py

**Próximo passo**: Integrar celery_beat_config.py no config/celery.py e configurar email backend
