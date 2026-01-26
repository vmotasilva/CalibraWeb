# Comandos para Deploy - Export Excel Planejamentos

## ✅ Verificação Pré-Deploy

```powershell
# 1. Verificar status do git
git status

# 2. Verificar se openpyxl está em requirements.txt
grep openpyxl requirements.txt

# 3. Listar arquivos modificados
git diff --name-only

# 4. Ver estatísticas
git diff --stat
```

## 📝 Commit

```powershell
# Adicionar todos os arquivos
git add procedures/
git add docs/
git add IMPLEMENTACAO_EXPORT_EXCEL_PLANEJAMENTOS.md
git add SUMARIO_EXPORT_EXCEL_PLANEJAMENTOS.py

# Verificar o que será commitado
git status

# Fazer commit
git commit -m "feat: add Excel export functionality for training planning

- Added Excel export for planning list with all filters preserved
- Added Excel export for planning details with 4 separate sheets
- Sheet 1: General information
- Sheet 2: Associated procedures
- Sheet 3: Participating collaborators
- Sheet 4: Training records

Features:
- Professional formatting (blue headers, borders, auto-width columns)
- UTF-8 encoding (supports accented characters)
- Login required (@login_required decorator)
- Performance optimized (select_related, prefetch_related)
- Compatible with Excel, Google Sheets, LibreOffice

Files:
- procedures/utils/export_utils.py (new PlanejamentoExcelExporter class)
- procedures/views/planejamento_views.py (2 new views)
- procedures/urls.py (2 new routes)
- procedures/templates/procedures/planejamento_lista.html (export button)
- procedures/templates/procedures/planejamento_detalhe.html (export button)
- docs/exportacao_excel_planejamentos.md (user guide)

Co-authored-by: Vinicius Mota <vinicius@calibra.local>"

# Se quiser verificar o commit antes de fazer push
git log --oneline -3
```

## 🚀 Push para Produção

```powershell
# Push para main (Railway fará deploy automático)
git push origin main

# Acompanhar o deploy
# Opção 1: Via Railway CLI
railway logs

# Opção 2: Dashboard do Railway
# Abra https://railway.app no navegador

# Esperar ~2-3 minutos para conclusão do deploy
```

## ✨ Verificação Pós-Deploy

```powershell
# 1. Acessar aplicação
# URL: https://calibraweb.up.railway.app

# 2. Verificar se botões aparecem
# - Acesse: Planejamento de Treinamentos
# - Procure por botão "Exportar Excel" (verde)

# 3. Testar export de lista
# - Clique em "Exportar Excel" na lista
# - Arquivo deve baixar como "planejamentos_lista.xlsx"

# 4. Testar export de detalhes
# - Abra um planejamento
# - Clique em "Exportar Excel"
# - Arquivo deve baixar como "planejamento_{ID}.xlsx"

# 5. Verificar logs por erros
railway logs | grep -i error
```

## 🔄 Rollback (Se Necessário)

```powershell
# Se ocorrer algum erro em produção

# 1. Revert do último commit
git revert HEAD

# 2. Push do revert
git push origin main

# 3. Railway detectará e fará redeploy com versão anterior
# Aguarde 2-3 minutos

# 4. Verificar que voltou ao normal
railway logs
```

## 📊 Monitoramento Contínuo

```powershell
# Ver logs em tempo real
railway logs -f

# Ver apenas erros
railway logs | grep ERROR

# Ver informações de performance
# (Acesse dashboard do Railway para gráficos)

# Se precisar verificar database
railway shell
```

## 🆘 Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'openpyxl'"
```powershell
# openpyxl não foi instalado
# Solução: Está em requirements.txt, Railway deve instalar

# Forçar rebuild:
railway redeploy
```

### Erro: "ImportError in export_utils"
```powershell
# Verificar sintaxe do arquivo
python -m py_compile procedures/utils/export_utils.py

# Se tiver erro de sintaxe, corrigir e fazer novo commit
git add procedures/utils/export_utils.py
git commit -m "fix: syntax error in export_utils"
git push origin main
```

### Botão não aparece no template
```powershell
# Verificar se templates foram salvos corretamente
git status

# Fazer collectstatic novamente
railway run python manage.py collectstatic --noinput

# Ou forçar redeploy
railway redeploy
```

## 📝 Changelog

```markdown
## [1.0.0] - 2026-01-16

### Added
- Excel export for training planning list
- Excel export for planning details (4 sheets)
- Professional formatting with colors and borders
- UTF-8 support for accented characters
- Filter preservation in list export
- Complete documentation

### Features
- Login required for all exports
- Performance optimized queries
- Compatible with Excel, Google Sheets, LibreOffice
- Automatic column width adjustment

### Files Changed
- procedures/utils/export_utils.py (NEW)
- procedures/views/planejamento_views.py
- procedures/urls.py
- procedures/templates/procedures/planejamento_lista.html
- procedures/templates/procedures/planejamento_detalhe.html

### Documentation
- docs/exportacao_excel_planejamentos.md
- IMPLEMENTACAO_EXPORT_EXCEL_PLANEJAMENTOS.md

### Tested On
- Windows 10 (local development)
- Railway (production environment)
- Excel 2016+, Google Sheets, LibreOffice Calc
```

## 🎯 Resumo de Deploy

| Passo | Comando | Tempo |
|-------|---------|-------|
| 1. Commit | `git commit -m "..."` | < 1min |
| 2. Push | `git push origin main` | < 1min |
| 3. Railway Build | Automático | ~1-2min |
| 4. Redeploy | Automático | ~1min |
| 5. Teste | Manual | ~2min |
| **Total** | | ~5min |

## ✅ Checklist Pré-Deploy

- [ ] Todos os arquivos foram adicionados ao git
- [ ] Commit message é descritivo
- [ ] openpyxl está em requirements.txt
- [ ] Código foi testado localmente
- [ ] Sem erros de sintaxe (python -m py_compile)
- [ ] Templates estão em UTF-8
- [ ] URLs estão configuradas corretamente
- [ ] Documentação está atualizada
- [ ] Pronto para fazer push

## ✅ Checklist Pós-Deploy

- [ ] Aplicação iniciou sem erros (railway logs)
- [ ] Página principal carrega normalmente
- [ ] Botões "Exportar Excel" aparecem nas telas
- [ ] Click em botão da lista baixa arquivo
- [ ] Click em botão do detalhe baixa arquivo
- [ ] Arquivo Excel abre normalmente
- [ ] Formatação está correta (azul, bordas, etc.)
- [ ] Dados estão completos e corretos
- [ ] Sem erros de encoding (acentuação OK)

---

**Pronto para deploy! 🚀**
