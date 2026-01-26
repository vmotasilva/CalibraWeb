# 🧪 GUIA DE TESTE - IMPORTAÇÃO DE MATRIZES

## Teste Local Completo

---

## ✅ Pré-requisitos

- [x] Servidor Django rodando em http://127.0.0.1:8000/
- [x] Autenticado no sistema (login realizado)
- [x] Arquivo CSV ou Excel disponível

---

## 🚀 Teste 1: Acesso à Tela

### Passos
1. Acesse: `http://127.0.0.1:8000/procedures/matrizes/importacao/`
2. Verifique se a página carrega
3. Observe o formulário de importação

### Resultado Esperado
✅ Página carrega sem erros  
✅ Formulário visível  
✅ Botões funcionando  
✅ Templates visíveis

---

## 🚀 Teste 2: Download de Template

### Passos
1. Clique em "Template CSV"
2. Salve o arquivo
3. Abra em um editor de texto

### Resultado Esperado
✅ Arquivo baixado  
✅ Extensão é `.csv`  
✅ Contém cabeçalhos corretos  
✅ Tem exemplos de dados

---

## 🚀 Teste 3: Importação com Dados Válidos

### Arquivo de Teste
Use o arquivo incluído:
```
c:\CalibraWeb\template_teste_importacao.csv
```

### Passos
1. Acesse: `/procedures/matrizes/importacao/`
2. Selecione "CSV"
3. Clique na área de upload
4. Selecione `template_teste_importacao.csv`
5. Clique "Processar Importação"

### Resultado Esperado
✅ Arquivo aceito  
✅ Redirecionado para resultados  
✅ Estatísticas exibidas  
✅ 3+ matrizes criadas  
✅ 7+ disciplinas criadas  
✅ Sem erros na importação

---

## 🚀 Teste 4: Validação de Erros

### Passos
1. Crie um arquivo CSV com dados inválidos:
```csv
Matriz Código|Matriz Nome|Disciplina Código|Disciplina Nome|...
|Operação|||...|
MAT002|Manutenção|DISC|||...
```

2. Faça upload do arquivo
3. Verifique erros reportados

### Resultado Esperado
✅ Erros identificados  
✅ Linhas com problemas marcadas  
✅ Mensagens claras de erro  
✅ Dados válidos ainda importados

---

## 🚀 Teste 5: Verificação de Dados Importados

### Verificar Matrizes
1. Acesse: `/procedures/matrizes/`
2. Procure pelas matrizes importadas (MAT001, MAT002, MAT003)

### Verificar Disciplinas
1. Clique em uma matriz
2. Veja disciplinas associadas

### Verificar Colaboradores
1. Clique em uma matriz
2. Clique em botão "Colaboradores"
3. Veja lista de colaboradores

### Resultado Esperado
✅ Matrizes visíveis  
✅ Disciplinas listadas  
✅ Colaboradores associados

---

## 🚀 Teste 6: Atualização de Dados Duplicados

### Passos
1. Crie um CSV com mesma matriz:
```csv
Matriz Código|Matriz Nome|...
MAT001|Operação Atualizada|...
```

2. **Marque** opção "Atualizar registros existentes"
3. Faça upload

### Resultado Esperado
✅ Matriz MAT001 foi atualizada  
✅ Nome mudou para "Operação Atualizada"  
✅ Aviso de atualização exibido

---

## 🚀 Teste 7: Colaboradores Não Encontrados

### Arquivo com Colaborador Inexistente
```csv
Matriz Código|Matriz Nome|...|Colaborador Matrícula|Colaborador Nome|...
MAT001|Operação|...|E999|Pessoa Inexistente|...
```

### Passos
1. Faça upload do arquivo
2. Verifique a seção de "Avisos"

### Resultado Esperado
✅ Matriz criada  
✅ Disciplina criada  
✅ Aviso sobre colaborador não encontrado  
✅ Importação continua normalmente

---

## 🚀 Teste 8: Excel (.xlsx)

### Passos
1. Clique "Template Excel"
2. Baixe e abra em Excel
3. Preencha com dados
4. Salve em formato Excel 2007 (.xlsx)
5. Faça upload

### Resultado Esperado
✅ Arquivo Excel aceito  
✅ Dados processados  
✅ Mesmos resultados que CSV

---

## 🚀 Teste 9: Interface Responsiva

### Testar em Diferentes Tamanhos
1. Desktop (1920x1080)
2. Tablet (768x1024)
3. Mobile (375x667)

### Resultado Esperado
✅ Layout se adapta  
✅ Botões funcionam em mobile  
✅ Formulário visível  
✅ Sem erros de rendering

---

## 🚀 Teste 10: Relatório Visual

### Passos
1. Faça uma importação
2. Observe a página de resultados
3. Verifique cada seção:
   - Estatísticas
   - Erros (se houver)
   - Avisos
   - Botões de ação

### Resultado Esperado
✅ Estatísticas visíveis  
✅ Números corretos  
✅ Cores diferenciadas por tipo  
✅ Botões funcionam

---

## 🚀 Teste 11: Segurança

### Testar CSRF
1. Abra DevTools (F12)
2. Verifique se há token CSRF no formulário
3. Tente submeter sem token (não vai funcionar)

### Testar Autenticação
1. Faça logout
2. Tente acessar `/procedures/matrizes/importacao/`
3. Deve redirecionar para login

### Resultado Esperado
✅ Token CSRF presente  
✅ Requer login  
✅ Proteção contra CSRF ativa

---

## 🚀 Teste 12: Performance

### Teste com Arquivo Grande
1. Crie arquivo CSV com 100 linhas
2. Faça upload
3. Cronometrize o tempo

### Resultado Esperado
✅ Processamento rápido (< 10 segundos)  
✅ Sem timeout  
✅ Resultados exibidos  
✅ Relatório completo

---

## 📋 Checklist de Testes

- [ ] Teste 1: Tela carrega corretamente
- [ ] Teste 2: Templates baixam
- [ ] Teste 3: Importação básica funciona
- [ ] Teste 4: Erros são detectados
- [ ] Teste 5: Dados aparecem no sistema
- [ ] Teste 6: Atualização de duplicatas funciona
- [ ] Teste 7: Avisos de colaborador não encontrado
- [ ] Teste 8: Excel funciona
- [ ] Teste 9: Interface responsiva
- [ ] Teste 10: Relatório visual correto
- [ ] Teste 11: Segurança ativa
- [ ] Teste 12: Performance boa

---

## ✅ Após os Testes

Se tudo passou:
1. ✅ Sistema está operacional
2. ✅ Pronto para produção
3. ✅ Documentação é suficiente
4. ✅ Usuários podem usar

Se encontrou problemas:
1. Verifique [TROUBLESHOOTING](./TROUBLESHOOTING_IMPORTACAO_MATRIZES.md)
2. Revise os arquivos de configuração
3. Contacte o suporte técnico

---

## 🎯 Resultado Final

Após completar todos os testes:

### Status de Qualidade
- **Funcionalidade:** ✅ OK
- **Interface:** ✅ OK
- **Segurança:** ✅ OK
- **Performance:** ✅ OK
- **Documentação:** ✅ OK

### Conclusão
🎉 **Sistema pronto para uso em produção!**

---

## 📞 Problemas Durante Testes?

Consulte:
1. [TROUBLESHOOTING](./TROUBLESHOOTING_IMPORTACAO_MATRIZES.md)
2. [GUIA DO USUÁRIO](./IMPORTACAO_MATRIZES_GUIA.md)
3. [ACESSO RÁPIDO](./ACESSO_RAPIDO_IMPORTACAO_MATRIZES.md)

---

**Data:** 12 de Janeiro de 2026  
**Versão:** 1.0  
**Status:** ✅ Guia de Teste Completo
