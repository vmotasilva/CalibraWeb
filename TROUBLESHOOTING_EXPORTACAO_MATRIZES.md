# 🆘 TROUBLESHOOTING - EXPORTAÇÃO DE MATRIZES

## 📋 Guia Rápido de Problemas e Soluções

---

## ❌ Problema: Botão de Exportação Não Aparece

### Sintomas:
- Não vejo o botão "Exportar" na tela de matrizes
- Vejo apenas "Importação em Massa" e "Nova Matriz"

### Causas Possíveis:
1. ❌ Página não carregou corretamente
2. ❌ Cache do navegador
3. ❌ Template não foi atualizado
4. ❌ Servidor não foi reiniciado

### Soluções:

**Solução 1: Limpar Cache**
```
Ctrl + Shift + Delete (Windows)
Cmd + Shift + Delete (Mac)
```
- Selecione "Cached images and files"
- Clique "Clear"
- Recarregue a página

**Solução 2: Recarregar Página**
```
F5 ou Ctrl + R
```

**Solução 3: Hard Refresh**
```
Ctrl + Shift + R (Windows)
Cmd + Shift + R (Mac)
```

**Solução 4: Reiniciar Servidor Django**
```powershell
# Terminal 1: Parar servidor
Ctrl + C

# Terminal 2: Reiniciar
python manage.py runserver 0.0.0.0:8000
```

---

## ❌ Problema: Arquivo Não Baixa

### Sintomas:
- Clico no botão "Exportar" mas nada acontece
- Não aparece na pasta de Downloads
- Nenhuma mensagem de erro

### Causas Possíveis:
1. ❌ Pop-up/Download bloqueado pelo navegador
2. ❌ Pasta de Downloads cheia ou protegida
3. ❌ Timeout na conexão
4. ❌ Erro no servidor (não visível)

### Soluções:

**Solução 1: Verificar Bloqueio de Pop-ups**
1. Clique no ícone de cadeado na URL bar
2. Procure por "Pop-ups"
3. Mude para "Allow"
4. Tente novamente

**Solução 2: Verificar Downloads**
1. Pressione `Ctrl + J` (Chrome/Edge)
2. Ou clique no ícone de Downloads
3. Procure por arquivo com timestamp
4. Se não está lá, verifique permissões

**Solução 3: Tentar Outro Navegador**
- Chrome
- Firefox
- Edge
- Safari

**Solução 4: Verificar Console (DevTools)**
```
F12 → Console tab
Procure por erros em vermelho
Anote a mensagem de erro exata
```

**Solução 5: Verificar Pasta de Downloads**
```powershell
# Windows
C:\Users\[seu_usuario]\Downloads
dir | findstr exportacao

# Se vazio, tente mudança de permissões
```

---

## ❌ Problema: Arquivo Está Vazio

### Sintomas:
- Arquivo baixa, mas abre vazio
- 0 bytes ou apenas headers
- CSV/Excel sem dados

### Causas Possíveis:
1. ❌ Nenhuma matriz cadastrada
2. ❌ Erro ao processar dados
3. ❌ Permissão de banco de dados

### Soluções:

**Solução 1: Verificar se Existem Matrizes**
1. Acesse `/procedures/matrizes/`
2. Verifique se lista está vazia
3. Se vazia, crie uma matriz de teste:
   - Clique "Nova Matriz"
   - Preencha os dados
   - Salve

**Solução 2: Verificar Banco de Dados**
```powershell
# No terminal do projeto
python manage.py shell

# Python shell
from procedures.models import MatrizHabilidade
print(MatrizHabilidade.objects.count())
# Se retornar 0, não há matrizes

# Sair
exit()
```

**Solução 3: Tentar Importação Primeiro**
1. Use arquivo de teste: `template_teste_importacao.csv`
2. Acesse `/procedures/matrizes/importacao/`
3. Faça upload e importação
4. Tente exportar novamente

---

## ❌ Problema: Erro Ao Abrir CSV no Excel

### Sintomas:
- Arquivo baixa com sucesso
- Excel abre mas dados parecem estranhos
- Colunas não aparecem corretamente
- Tudo em uma coluna

### Causas Possíveis:
1. ❌ Encoding incorreto
2. ❌ Delimitador não reconhecido (esperava , mas é |)
3. ❌ Versão Excel antiga

### Soluções:

**Solução 1: Importação Correta no Excel**
1. Abra Excel
2. Clique `File → Open`
3. Selecione o arquivo `.csv`
4. Aparecerá "Text Import Wizard":
   - Step 1: Selecione "Delimited"
   - Step 2: Desmarque "Tab" e "Comma"
   - **Marque "Other" e digite: `|`**
   - Step 3: Verifique preview
   - Clique "Finish"

**Solução 2: Usar Google Sheets (Online)**
1. Acesse `sheets.google.com`
2. File → Open → Upload
3. Selecione o arquivo `.csv`
4. Sheets importa automaticamente

**Solução 3: Usar LibreOffice Calc (Grátis)**
1. Instale LibreOffice (se não tiver)
2. Abra o arquivo .csv com LibreOffice
3. Mesma configuração do Excel (delimitador |)

**Solução 4: Abrir em Editor de Texto**
1. Clique direito no arquivo
2. "Open with → Notepad"
3. Visualize os dados brutos
4. Se vir pipes (|) correctamente, problema é só na formatação

---

## ❌ Problema: Erro Ao Abrir Excel (.xlsx)

### Sintomas:
- Arquivo não abre no Excel
- Mensagem: "Excel não consegue abrir"
- Arquivo corrompido?

### Causas Possíveis:
1. ❌ Arquivo incompleto (download interrompido)
2. ❌ Versão Excel muito antiga
3. ❌ Permissão de leitura

### Soluções:

**Solução 1: Download Novamente**
1. Verifique tamanho do arquivo
2. Se muito pequeno (< 1KB), download falhou
3. Tente novamente
4. Verifique conexão

**Solução 2: Atualizar Excel**
1. Abra Excel
2. File → Account → Update Options
3. Instale atualizações
4. Reinicie Excel

**Solução 3: Usar Google Sheets**
1. Acesse `sheets.google.com`
2. File → Open → Upload
3. Selecione arquivo .xlsx
4. Sheets abre e converte

**Solução 4: Usar LibreOffice Calc**
1. Instale LibreOffice (grátis)
2. Abra arquivo .xlsx
3. Salve como Excel se necessário

**Solução 5: Reparar Arquivo**
```powershell
# Windows PowerShell
# Copiar arquivo
Copy-Item "exportacao_matrizes_*.xlsx" "backup.xlsx"

# Tente abrir backup
# Se funcionar, use a cópia
```

---

## ❌ Problema: Erro 404 em Rota de Exportação

### Sintomas:
- Clico em exportar e recebo erro 404
- "Page not found"
- URL é `/procedures/matrizes/exportar/csv/`

### Causas Possíveis:
1. ❌ URL não foi registrada em urls.py
2. ❌ Servidor não foi reiniciado
3. ❌ Erro no typo da rota

### Soluções:

**Solução 1: Verificar URLs**
1. Abra `procedures/urls.py`
2. Procure por: `exportar_matrizes`
3. Verifique se a linha existe:
```python
path('matrizes/exportar/<str:formato>/', habilidades_views.exportar_matrizes_view, name='exportar_matrizes'),
```

**Solução 2: Reiniciar Servidor**
```powershell
Ctrl + C  # Parar
python manage.py runserver 0.0.0.0:8000  # Reiniciar
```

**Solução 3: Verificar Nome da View**
1. Abra `procedures/views/habilidades_views.py`
2. Procure: `def exportar_matrizes_view`
3. Verifique se função existe

**Solução 4: Coletar Static Files** (se em produção)
```powershell
python manage.py collectstatic --noinput
```

---

## ❌ Problema: Erro 500 (Erro do Servidor)

### Sintomas:
- Clico em exportar
- Recebo "Internal Server Error"
- Ou erro genérico 500

### Causas Possíveis:
1. ❌ Erro na view (exceção não tratada)
2. ❌ Permissão de banco de dados
3. ❌ Modelos incorretos
4. ❌ Dependência faltando (openpyxl)

### Soluções:

**Solução 1: Verificar Logs**
1. Veja o terminal onde Django está rodando
2. Procure por mensagens de erro em vermelho
3. Anote a mensagem exata

**Solução 2: Instalar Dependências**
```powershell
pip install openpyxl  # Se não estiver instalado
pip install -r requirements.txt  # Instalar todas
```

**Solução 3: Verificar Permissões de Arquivo**
```powershell
# Arquivo de banco de dados
cd c:\CalibraWeb
dir db.sqlite3

# Se não encontrar, banco está em outro lugar
find . -name "*.sqlite3"
```

**Solução 4: Debug no Terminal**
```powershell
# Terminal Python
python manage.py shell

# Testar exportação manualmente
from procedures.utils.exportacao_matriz import ExportadorMatrizHabilidade
exp = ExportadorMatrizHabilidade()
output, filename = exp.exportar_csv()
print(f"Exportado: {filename}")
print(f"Tamanho: {len(output.getvalue())} bytes")
```

---

## ❌ Problema: Arquivo Muito Grande

### Sintomas:
- Exportação demora muito tempo
- Arquivo resultante é huge (> 100 MB)
- Abre lentamente no Excel

### Causas Possíveis:
1. ❌ Muitas matrizes/disciplinas/colaboradores
2. ❌ Dados duplicados
3. ❌ Formato Excel (maior que CSV)

### Soluções:

**Solução 1: Usar CSV em vez de Excel**
- CSV é 50% menor
- Abre mais rápido
- Funciona em Python/Pandas

**Solução 2: Fragmentar Exportação**
```python
# Exportar apenas uma matriz
from procedures.models import MatrizHabilidade
matriz = MatrizHabilidade.objects.get(codigo='MAT001')
# Criar filtro customizado
```

**Solução 3: Limpar Dados Antigos**
- Remover matrizes inativas
- Excluir duplicatas
- Arquivar dados históricos

**Solução 4: Usar Pandas para Processar**
```python
import pandas as pd
df = pd.read_csv('exportacao_matrizes.csv', sep='|')
# Remover duplicatas
df = df.drop_duplicates()
# Salvar versão otimizada
df.to_csv('exportacao_otimizada.csv', sep='|', index=False)
```

---

## ❌ Problema: Colaboradores Faltam na Exportação

### Sintomas:
- Exporto arquivo
- Algumas disciplinas não têm colaboradores
- Esperava mais registros

### Causas Possíveis:
1. ❌ Colaboradores não associados corretamente
2. ❌ Matrícula não preenchida
3. ❌ Filtro de permissões

### Soluções:

**Solução 1: Verificar Associações**
1. Acesse `/procedures/matrizes/`
2. Clique em uma matriz
3. Verifique seção de colaboradores
4. Se vazia, nenhum será exportado

**Solução 2: Verificar Matrículas**
1. Abra o arquivo exportado
2. Procure por linhas vazias na coluna "Colaborador Matrícula"
3. Se vazia, não foi associado

**Solução 3: Usar Console do Django**
```python
from procedures.models import ColaboradorMatrizHabilidade
# Contar associações
print(ColaboradorMatrizHabilidade.objects.count())
# Se 0, nenhuma associação foi feita
```

---

## ❌ Problema: Especiais Caracteres Quebrados

### Sintomas:
- Abre arquivo com caracteres estranhos
- Acentos aparecem como "?"
- Especiais caracteres ilegíveis

### Causas Possíveis:
1. ❌ Encoding UTF-8 não configurado
2. ❌ Excel usando encoding errado
3. ❌ Banco de dados com encoding diferente

### Soluções:

**Solução 1: Excel - Configurar Encoding**
1. File → Open
2. Em "Open" dialog, clique arquivo CSV
3. Text Import Wizard → Step 1
4. Mude "File origin" para "UTF-8"
5. Clique "Finish"

**Solução 2: Usar Editor de Texto**
1. Clique direito no arquivo
2. "Open with → Notepad"
3. Se caracteres corretos aqui, problema é Excel
4. Tente outra aplicação (Google Sheets, LibreOffice)

**Solução 3: Reencrypt Arquivo**
```powershell
# Converter CSV para UTF-8 explícito
$content = Get-Content "exportacao_matrizes.csv" -Encoding UTF8
$content | Out-File "exportacao_matrizes_utf8.csv" -Encoding UTF8
```

---

## ✅ Verificação Rápida (Health Check)

Se algo não funciona, execute este checklist:

```
☐ 1. Acesse http://127.0.0.1:8000/procedures/matrizes/
      Resposta esperada: Lista de matrizes carrega

☐ 2. Vejo botão "Exportar" amarelo?
      Se não: Limpar cache (Ctrl+Shift+R)

☐ 3. Clique em "Exportar → CSV"
      Resposta esperada: Arquivo baixa em 1-2 segundos

☐ 4. Verifique pasta Downloads
      Resposta esperada: Arquivo "exportacao_matrizes_*.csv" existe

☐ 5. Abra arquivo em editor de texto
      Resposta esperada: Vê dados com pipes (|) entre colunas

☐ 6. Tente abrir em Excel/Google Sheets
      Resposta esperada: Dados formatados corretamente

☐ 7. Se tudo funciona: ✅ Sistema OK!
      Se algo falhou: Vá para solução específica acima
```

---

## 📞 Se Ainda Não Funcionar

1. Anote exatamente qual erro você recebe
2. Abra o DevTools (F12)
3. Vá para "Network" tab
4. Tente exportar novamente
5. Procure pelo request que falhou
6. Contacte suporte com essa informação

---

**Data:** 12 de Janeiro de 2026  
**Versão:** 1.0  
**Status:** ✅ Troubleshooting Completo
