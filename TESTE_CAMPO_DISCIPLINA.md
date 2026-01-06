# GUIA DE TESTE: Campo Disciplina Duplicado + Identificação de Procedimentos

## ✅ Checklist de Validação

### Passo 1: Abrir Novo Planejamento
- [ ] Abra: `http://localhost:8000/procedures/planejamentos/novo/`
- [ ] Formulário carrega corretamente
- [ ] Nenhuma duplicação visual de campos

### Passo 2: Testar Origem "MATRIZ" 
- [ ] Selecione **Origem: "Matriz de Habilidades"**
- [ ] Aparecem campos:
  - [ ] Seletor de Matriz
  - [ ] Seletor de Disciplina (desabilitado até selecionar Matriz)
  - [ ] Seção "Sugestões Carregadas!" (oculta até selecionar Disciplina)

### Passo 3: Selecionar Matriz
- [ ] Selecione uma **Matriz de Habilidades** (ex: "RUN - Revista de Utilidades e Não-tecnicismo")
- [ ] Campo Disciplina é habilitado
- [ ] Lista de Disciplinas aparece
- [ ] Nenhum erro no console (F12)

### Passo 4: Selecionar Disciplina
- [ ] Selecione uma **Disciplina** (ex: "Fitagem")
- [ ] **[IMPORTANTE]** Verificar no console (F12):
  - Abra: F12 → Aba "Console"
  - Procure por mensagens com prefixo `[INFO]` ou `[DEBUG]`
  - Deve ver: `[OK] Procedimentos encontrados: X` ou `[AVISO] Nenhum procedimento encontrado`

#### Comportamento Esperado:

**Cenário 1: Procedimentos Encontrados ✅**
```
[INFO] Carregando procedimentos para disciplina ID: 2
[DEBUG API Response]: {...}
[OK] Procedimentos encontrados: 4
```
- [ ] Seção "Sugestões Carregadas!" aparece
- [ ] Badge "Procedimentos" mostra número > 0
- [ ] Tabela de Procedimentos se preenche automaticamente
- [ ] Nenhuma mensagem de aviso

**Cenário 2: Nenhum Procedimento ⚠️**
```
[INFO] Carregando procedimentos para disciplina ID: 5
[DEBUG API Response]: {...}
[AVISO] Nenhum procedimento encontrado para disciplina ID: 5
```
- [ ] Seção "Sugestões Carregadas!" aparece
- [ ] Badge "Procedimentos" mostra 0
- [ ] Mensagem: "Nenhum procedimento foi encontrado para esta disciplina"
- [ ] Link "Verificar dados" presente

### Passo 5: Colaboradores Sugeridos
- [ ] Badge "Colaboradores Sugeridos" mostra número
- [ ] Lista de colaboradores aparece com competência
- [ ] Botão "Adicionar Colaboradores Sugeridos" visível (se houver colaboradores)
- [ ] [ ] Clique no botão para adicionar

### Passo 6: Submeter Formulário
- [ ] Clique em **"Salvar"**
- [ ] Formulário submete corretamente
- [ ] Planejamento é criado
- [ ] [ ] **[IMPORTANTE]** Abra o registro criado para verificar:
  - A Disciplina foi salva corretamente no campo oculto
  - Os Procedimentos foram adicionados
  - Os Colaboradores foram adicionados

### Passo 7: Debug (se necessário)
Se nenhum procedimento aparecer, teste a API manualmente:

**URL de Debug**:
```
http://localhost:8000/procedures/api/debug-disciplina/?disciplina_id=2
```

**Resposta esperada**:
```json
{
  "debug": {
    "disciplina_id": 2,
    "disciplina_nome": "Fitagem",
    "DisciplinaProcedimento_count": 4,
    "procedimentos_associados": [...],
    "total_procedimentos_sistema": 50
  }
}
```

## 🐛 Resolução de Problemas

### Problema: "Campo Disciplina aparece duas vezes"
- ❌ **NÃO DEVE ACONTECER** (foi corrigido)
- Se acontecer: Limpe cache (Ctrl+Shift+Del) e recarregue

### Problema: "Nenhum procedimento aparece"

**Opção 1: Criar Associação Explícita (Recomendado)**
1. Abra Django Admin: `http://localhost:8000/admin/`
2. Vá em: **Procedures > Disciplina Procedimento**
3. Clique em "Add Disciplina Procedimento"
4. Selecione:
   - **Disciplina**: (aquela que quer associar)
   - **Procedimento**: (aquele que quer adicionar)
   - **Ordem**: 1
5. Salve
6. Recarregue o formulário → Procedimento deve aparecer

**Opção 2: Verificar Nomenclatura**
- Se DisciplinaProcedimento vazio, API tenta match por nome
- Exemplo: Disciplina "Fitagem" procura por procedimentos com "Fitagem" no nome
- [ ] Verifique se nomes conferem

### Problema: Console mostra erros de requisição
- [ ] Verifique se servidor está rodando
- [ ] Verifique URL da API nos logs
- [ ] Teste a URL diretamente no navegador

## 📊 Teste de Cobertura

| Funcionalidade | Status | Observações |
|---|---|---|
| Campo origem visível | ✅ | Rádio buttons aparecem |
| Matriz/Disciplina appear quando MATRIZ | ✅ | Hidden section se comporta correto |
| Disciplina se preenche automaticamente | ✅ | Via hidden input |
| Procedimentos carregam | ✅ | Com 3 estratégias de fallback |
| Colaboradores sugerem | ✅ | Com exclusão de N/A |
| Botão adicionar sugeridos | ✅ | Adiciona todos |
| Sem duplicação visual | ✅ | Campo oculto, não duplicado |
| Form submete corretamente | ✅ | Testado com ID: 2 |

## 🔍 Validação de Console (F12)

Abra o console e procure por estes padrões:

✅ **Esperado ver**:
```javascript
[INFO] Carregando procedimentos para disciplina ID: X
[OK] Procedimentos encontrados: N
[INFO] Colaboradores sugeridos carregados: N
```

❌ **NÃO deve ver**:
```javascript
Uncaught ReferenceError: disciplinaField is not defined
Cannot read property 'classList' of null
GET /procedures/api/...=undefined 404
```

## 📝 Relatório de Teste

Após completar os passos, preencha:

**Data**: ___________
**Navegador**: ___________
**Teste Passou**: [ ] SIM [ ] NÃO

**Observações**:
```
_________________________________
_________________________________
_________________________________
```

**Screenshots (opcional)**:
- Formulário com campos visíveis
- Console com logs de sucesso
- Planejamento criado e salvo

---

**Dúvidas?** 
- Verifique a seção "Debug" acima
- Veja arquivo `FIX_DISCIPLINA_DUPLICADA.md` para detalhes técnicos
- Abra Django Admin para criar associações manuais
