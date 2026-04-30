# 🔧 TROUBLESHOOTING - IMPORTAÇÃO DE MATRIZES

## Problemas Comuns e Soluções

---

## ❌ Erro: "ValueError: Need 2 values to unpack in for loop"

**Status:** ✅ **RESOLVIDO**

### Problema
Template de importação falhava ao renderizar RadioSelect.

### Solução
Corrigido o loop no template `matriz_importacao.html` para iterar corretamente sobre os widgets.

### Arquivo Corrigido
- `procedures/templates/procedures/matriz_importacao.html`

---

## ❌ Erro: "Arquivo não encontrado" ao fazer upload

### Verificar:
1. Arquivo tem extensão correta? (`.csv` ou `.xlsx`)
2. Tamanho do arquivo não está muito grande?
3. Arquivo não tem caracteres especiais no nome?

### Solução:
- Renomeie o arquivo para algo simples: `dados.csv` ou `matrizes.xlsx`
- Verifique se o arquivo não está corrompido

---

## ❌ Erro: "Cabeçalho não encontrado"

### Causa:
Arquivo não tem cabeçalhos na primeira linha ou cabeçalhos com nomes errados.

### Verificar Colunas Exatas:
```
1. Matriz Código
2. Matriz Nome
3. Disciplina Código
4. Disciplina Nome
5. Disciplina Descrição
6. Disciplina Prioridade
7. Disciplina Obrigatoriedade
8. Colaborador Matrícula
9. Colaborador Nome
10. Colaborador Email
```

### Solução:
1. Baixe o template novamente
2. Use copiar/colar para garantir os nomes corretos
3. Verifique se não há espaços extras

---

## ❌ Erro: "Matriz código e nome são obrigatórios"

### Causa:
Linhas com campos vazios obrigatórios.

### Campos Obrigatórios:
- **Matriz Código** (único)
- **Matriz Nome**
- **Disciplina Nome**

### Solução:
Preencha esses campos para todas as linhas.

---

## ❌ Aviso: "Colaborador não encontrado"

### Causa:
Sistema não encontrou o colaborador no banco de dados.

### Procura Por:
1. Matrícula (exato)
2. Nome completo (case-insensitive)
3. Email (case-insensitive)

### Solução:
Verifique os dados do colaborador no sistema:
- Menu → RH → Colaboradores
- Confira matrícula, nome ou email

### Nota:
Isso é um **aviso**, não um erro. A importação continua normalmente.

---

## ❌ Erro: "Formato não suportado"

### Causa:
Arquivo tem extensão que não é `.csv` ou `.xlsx`.

### Extensões Válidas:
- `.csv` ✅
- `.xlsx` ✅
- `.xls` ❌ (muito antigo, use .xlsx)
- `.txt` ❌ (use .csv)

### Solução:
Salve o arquivo no formato correto:
- **Excel:** Salve como "Excel 2007-365 (*.xlsx)"
- **CSV:** Salve como "CSV (Delimitado por vírgula)"

---

## ❌ Erro: Linhas duplicadas não são atualizadas

### Causa:
Opção "Atualizar registros existentes" não está marcada.

### Solução:
Na tela de importação, marque a opção:
```
☑ Atualizar registros existentes
```

---

## ❌ Erro: "Caracteres não reconhecidos" (encoding)

### Causa:
Arquivo tem encoding diferente (Latin-1, CP1252, etc).

### Solução:
1. Abra o arquivo em um editor
2. Salve como **UTF-8**:
   - Notepad++: Encoding → Encode in UTF-8
   - Excel: Salve e abra em Notepad, Encoding → UTF-8

### Sistema Detecta:
O sistema tenta automaticamente UTF-8 e Latin-1.

---

## ❌ Erro: Disciplinas com código vazio

### Causa:
Campo "Disciplina Código" deixado em branco.

### Solução:
Deixe em branco e o sistema gera automaticamente (DISC001, DISC002, etc).

### Ou:
Preencha com códigos únicos (DISC001, DISC002, etc).

---

## ❌ Erro: "Arquivo muito grande"

### Limite:
Não há limite teórico, mas recomenda-se:
- **CSV:** Até 10.000 linhas
- **Excel:** Até 5.000 linhas

### Se Exceder:
1. Divida em múltiplos arquivos
2. Importe um arquivo por vez
3. Aguarde entre importações

---

## ❌ Erro: Servidor retorna 500

### Verificar:
1. Servidor está rodando? `python manage.py runserver`
2. Arquivo corrompido?
3. Banco de dados acessível?

### Solução:
1. Verifique logs do servidor
2. Reinicie o Django
3. Verifique banco de dados

---

## ❌ Aviso: "Matrizes Atualizadas: 0"

### Causa:
Opção "Atualizar existentes" marcada, mas nenhuma matriz duplicada encontrada.

### Verificar:
1. Código da matriz é igual ao existente?
2. Verifique em: Menu → Procedimentos → Matrizes

### Nota:
Isso é normal se estão sendo criadas matrizes novas.

---

## ✅ Como Verificar Dados Importados

### 1. Matrizes Criadas
```
Menu → Procedimentos → Matrizes de Habilidades
```
Veja a lista de matrizes com card visual.

### 2. Disciplinas Criadas
```
Clique em uma Matriz → Veja disciplinas listadas
```

### 3. Colaboradores Associados
```
Clique em uma Matriz → Botão "Colaboradores"
Veja lista de colaboradores associados
```

---

## 🔍 Debug: Ver Detalhes da Importação

### Arquivo de Teste
Um arquivo CSV de teste está disponível em:
```
c:\CalibraWeb\template_teste_importacao.csv
```

### Usar para Testar:
1. Acesse `/procedures/matrizes/importacao/`
2. Faça upload do arquivo de teste
3. Veja os resultados esperados

---

## 💾 Backup e Recuperação

### Antes de Importar:
1. Faça backup do banco de dados:
   ```
   cp db.sqlite3 db.sqlite3.backup
   ```

2. Sempre teste com arquivo pequeno primeiro

### Se Algo Derem Errado:
1. Restaure backup:
   ```
   cp db.sqlite3.backup db.sqlite3
   ```

2. Reinicie Django

---

## 🎯 Checklist de Verificação

- [ ] Arquivo tem formatação correta?
- [ ] Cabeçalhos estão exatos?
- [ ] Campos obrigatórios preenchidos?
- [ ] Encoding é UTF-8?
- [ ] Colaboradores existem no sistema?
- [ ] Opção "Atualizar existentes" marcada (se aplicável)?
- [ ] Servidor está rodando?
- [ ] Login realizado?

---

## 📞 Suporte Técnico

### Se persistir o erro:
1. Verifique esta documentação
2. Revise o arquivo de entrada
3. Contacte administrador com:
   - Mensagem de erro exata
   - Arquivo de entrada (se possível)
   - Print de screen

---

## 🚀 Próximos Passos

Se tudo funcionar:
1. Importe dados em lote
2. Valide matrizes criadas
3. Revise disciplinas associadas
4. Confirme colaboradores vinculados

---

**Status:** ✅ Todos os problemas conhecidos foram documentados e solucionados.

**Última atualização:** 12 de Janeiro de 2026
