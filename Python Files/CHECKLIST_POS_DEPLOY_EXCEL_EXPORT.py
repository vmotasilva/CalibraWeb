#!/usr/bin/env python
"""
CHECKLIST PÓS-DEPLOY - CalibraWEB
Data: 2026-01-16
Versão: 1.0

Este arquivo contém o checklist completo para verificar se o deploy
foi bem-sucedido na produção (Railway).
"""

CHECKLIST_POS_DEPLOY = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    ✅ CHECKLIST PÓS-DEPLOY                               ║
║                  CalibraWEB - Produção (Railway)                         ║
║                        2026-01-16                                         ║
╚════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ VERIFICAÇÃO INICIAL (PRIMEIROS 5 MINUTOS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ LOGS DO RAILWAY
  □ Abrir: https://railway.app/project/[PROJECT_ID]
  □ Verificar: "Application started" ou similar
  □ Procurar por: ERRO, EXCEPTION, ERROR
  □ Esperado: ✅ Logs verdes, sem erros críticos

□ STATUS DO SERVIDOR
  □ Ping: curl -I https://calibraweb.up.railway.app
  □ Resultado esperado: HTTP 200, 301 (redirect), ou 302 (login)
  □ Resultado NÃO OK: 502 Bad Gateway, 503 Service Unavailable, 504 Timeout

□ CONTAINERS RODANDO
  □ Railway Dashboard: Verificar status dos containers
  □ Web container: ✅ Running
  □ Worker container: ✅ Running (Celery)
  □ Beat container: ✅ Running (Celery Beat)
  □ CPU Usage: Normal (< 30%)
  □ Memory: Normal (< 200 MB)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2️⃣ VERIFICAÇÃO DE FUNCIONALIDADES EXISTENTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ LOGIN
  □ Acesse: https://calibraweb.up.railway.app/login
  □ Entre com: username e password corretos
  □ Resultado esperado: ✅ Redirecionado para dashboard

□ DASHBOARD
  □ Acesse: Dashboard após login
  □ Verificar: Gráficos carregam
  □ Verificar: Dados atualizados
  □ Tempo de carregamento: < 2 segundos

□ BANCO DE DADOS
  □ Admin: /admin/
  □ Acessar models principais
  □ Verificar dados existentes
  □ Resultado esperado: ✅ Dados intactos

□ FEATURES EXISTENTES
  □ Procedimentos: Listar, criar, editar ✅
  □ Planejamentos: Listar, criar, editar ✅
  □ Colaboradores: Listar, editar ✅
  □ Treinamentos: Visualizar, atualizar ✅
  □ RH: Dashboard, estatísticas ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3️⃣ VERIFICAÇÃO DAS NOVAS FEATURES (EXCEL EXPORT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ BOTÃO NA LISTA
  □ Acesse: Planejamentos → /procedures/planejamentos/
  □ Procure por: Botão "Exportar Excel" (verde, ícone de planilha)
  □ Resultado esperado: ✅ Botão visível
  □ Posição esperada: Lado direito, acima da tabela

□ EXPORTAR LISTA (TESTE 1)
  □ Clique no botão "Exportar Excel"
  □ Arquivo deve baixar: planejamentos_lista.xlsx
  □ Tamanho esperado: 50-500 KB
  □ Abra no Excel/Sheets
  □ Verificar:
     □ 12 colunas: ID, Título, Status, Origem, Datas, etc.
     □ Cabeçalho em azul (#0D6EFD)
     □ Bordas em todas as células
     □ Acentuação preservada (sem ? ou garbled text)
     □ Primeira linha congelada
  □ Resultado esperado: ✅ Tudo OK

□ EXPORTAR LISTA COM FILTROS (TESTE 2)
  □ Aplique filtro: Status = PLANEJADO
  □ Clique: "Filtrar"
  □ Clique: "Exportar Excel"
  □ Arquivo deve conter: APENAS planejamentos com status PLANEJADO
  □ Linha de rodapé: Deve mostrar número correto de linhas
  □ Resultado esperado: ✅ Filtro preservado no export

□ BOTÃO NO DETALHE
  □ Acesse: Um planejamento específico
  □ Procure por: Botão "Exportar Excel" (verde, barra de ações)
  □ Posição: Entre "Alterar Status" e "Voltar"
  □ Resultado esperado: ✅ Botão visível

□ EXPORTAR DETALHES (TESTE 3)
  □ Clique: "Exportar Excel" no detalhe
  □ Arquivo deve baixar: planejamento_{ID}.xlsx
  □ Abra no Excel/Sheets
  □ Verificar abas:
     □ Aba 1 "Informações": Dados completos do planejamento
     □ Aba 2 "Procedimentos": Lista de procedimentos (código, nome)
     □ Aba 3 "Colaboradores": Lista de colaboradores (nome, matrícula, cargo)
     □ Aba 4 "Registros de Treinamento": Histórico de treinamentos
  □ Todas as abas: Cabeçalho azul, bordas, formatação correta
  □ Resultado esperado: ✅ 4 abas com dados corretos

□ PERFORMANCE DO EXPORT
  □ Export lista com 100+ planejamentos: < 2 segundos
  □ Export detalhes com muitos procedimentos: < 1 segundo
  □ Download do arquivo: < 5 segundos
  □ Resultado esperado: ✅ Rápido e responsivo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4️⃣ VERIFICAÇÃO DE SEGURANÇA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ AUTENTICAÇÃO
  □ Tentar acessar export sem login:
     /procedures/planejamentos/export/lista-excel/
  □ Resultado esperado: ✅ Redirecionado para /login

□ PERMISSÕES
  □ Usuário comum (não admin): Pode ver apenas seus dados
  □ Admin: Pode ver todos os dados
  □ Resultado esperado: ✅ Segurança respeitada

□ DADOS SENSÍVEIS
  □ Verificar que arquivo NÃO contém:
     □ Senhas
     □ Tokens
     □ URLs internas sensíveis
     □ Informações confidenciais
  □ Resultado esperado: ✅ Nenhum dado sensível

□ SSL/TLS
  □ URL deve ser HTTPS
  □ Certificado válido
  □ Resultado esperado: ✅ Conexão segura (ícone de cadeado)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5️⃣ VERIFICAÇÃO DE BANCO DE DADOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ MIGRAÇÕES
  □ Verificar logs: "Running migrations"
  □ Resultado esperado: ✅ Sem erros de migração

□ CONEXÃO POSTGRESQL
  □ Verificar que dados estão sendo lidos
  □ Atualizar planejamento e verificar se persiste
  □ Resultado esperado: ✅ Banco funcionando

□ INTEGRIDADE DOS DADOS
  □ Comparar dados do export com admin
  □ Verificar totalizadores (count, sum)
  □ Resultado esperado: ✅ Dados íntegros

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6️⃣ VERIFICAÇÃO DE CACHE E REDIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ REDIS CONNECTION
  □ Logs devem mostrar conexão com Redis
  □ Resultado esperado: ✅ Redis conectado

□ CACHE FUNCIONANDO
  □ Acessar página e verificar se carrega rápido (cache)
  □ Atualizar conteúdo e verificar se cache se invalida
  □ Resultado esperado: ✅ Cache funcionando

□ CELERY TASKS
  □ Verificar se background tasks estão rodando
  □ Resultado esperado: ✅ Worker respondendo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7️⃣ VERIFICAÇÃO DE COMPATIBILIDADE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ EXCEL
  □ Abrir arquivo com: Microsoft Excel 2016+
  □ Resultado esperado: ✅ Abre sem problemas

□ GOOGLE SHEETS
  □ Upload para Google Sheets
  □ Resultado esperado: ✅ Importa corretamente

□ LIBREOFFICE / OPENOFFICE
  □ Abrir arquivo
  □ Resultado esperado: ✅ Formatação preservada

□ NAVEGADORES
  □ Chrome/Edge: ✅
  □ Firefox: ✅
  □ Safari: ✅
  □ Downloads funcionando: ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8️⃣ VERIFICAÇÃO DE LOGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ ERROS CRÍTICOS
  □ Comando: railway logs | grep -i error
  □ Resultado esperado: ✅ Nenhum erro relacionado a export

□ WARNINGS
  □ Comando: railway logs | grep -i warning
  □ Resultado esperado: ✅ Warnings aceitáveis (depreciações, etc.)

□ PERFORMANCE
  □ Comando: railway logs | grep -i latency
  □ Resultado esperado: ✅ Latência aceitável (< 500ms para export)

□ REQUESTS
  □ Verificar: Total de requisições
  □ Resultado esperado: ✅ Taxa normal de requisições

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
9️⃣ VERIFICAÇÃO DE DOCUMENTAÇÃO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ README.md
  □ Contém instruções claras
  □ Linhas de início rápido (Quick Start)
  □ Resultado esperado: ✅ Documentação clara

□ docs/exportacao_excel_planejamentos.md
  □ Guia de uso para end-users
  □ Exemplos práticos
  □ Troubleshooting
  □ Resultado esperado: ✅ Documentação completa

□ DEPLOY_EXPORT_EXCEL_COMANDOS.md
  □ Instruções de deploy
  □ Checklist pré/pós-deploy
  □ Resultado esperado: ✅ Documentação técnica

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔟 VERIFICAÇÃO FINAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ TUDO FUNCIONANDO?
  □ Features antigas: ✅ Sem regressão
  □ Novas features: ✅ Funcionando perfeitamente
  □ Performance: ✅ Aceitável
  □ Segurança: ✅ Sem vulnerabilidades
  □ Documentação: ✅ Completa
  □ Logs: ✅ Sem erros críticos

□ ROLLBACK NÃO NECESSÁRIO?
  □ Resultado: ✅ SIM, Deploy bem-sucedido!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RESUMO DOS TESTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total de verificações: 50+
Críticas: 15
Funcionais: 35

Status esperado: 100% ✅

Se todas as verificações passarem:
   🎉 DEPLOY FOI BEM-SUCEDIDO! 🎉

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Se alguma verificação FALHAR:
   1. Anotar qual falhou
   2. Verificar logs do Railway
   3. Se crítico: fazer rollback
   4. Se menor: corrigir e fazer novo push

╚════════════════════════════════════════════════════════════════════════════╝
"""

print(CHECKLIST_POS_DEPLOY)

# Exportar para arquivo
with open('CHECKLIST_POS_DEPLOY.md', 'w', encoding='utf-8') as f:
    f.write(CHECKLIST_POS_DEPLOY)

print("\n✅ Checklist salvo em: CHECKLIST_POS_DEPLOY.md")
