# 🧪 Como Testar o Formulário com Modals

## ✅ Pré-requisitos
- Django rodando em http://localhost:8000
- Usuário autenticado
- Colaboradores e Procedimentos cadastrados

## 📝 Passos para Testar

### 1. Abra o Navegador
```
http://localhost:8000/procedures/planejamentos/novo/
```

### 2. Verifique se Vê:
- ✅ Campo "Colaboradores" com botão "Adicionar Colaborador"
- ✅ Campo "Procedimento" (se selecionar origem LIVRE) com botão "Adicionar Procedimento"
- ✅ Ambos com lista vazia ("Nenhum colaborador selecionado")

### 3. Teste Modal de Colaboradores
```
1. Clique em "Adicionar Colaborador"
2. Modal abre com lista de colaboradores
3. Busque por nome (ex: "João")
4. Marque 2-3 colaboradores
5. Clique em "Adicionar"
6. Modal fecha
7. Verifique que os colaboradores aparecem na lista
8. Veja o botão ✕ ao lado de cada nome
```

### 4. Teste Remoção
```
1. Clique no ✕ de um colaborador
2. Colaborador desaparece da lista
3. Se remover todos, volta para "Nenhum colaborador selecionado"
```

### 5. Teste Modal de Procedimentos (se origem=LIVRE)
```
1. Selecione origem "LIVRE"
2. Campo "Procedimento" aparece
3. Clique em "Adicionar Procedimento"
4. Modal abre com procedimentos
5. Busque por código ou nome
6. Selecione 1 procedimento
7. Clique em "Adicionar"
8. Procedimento aparece na lista
```

### 6. Teste Busca nos Modals
```
1. Abra modal de colaboradores
2. Digite "mar" na busca
3. Veja apenas colaboradores com "mar" no nome
4. Limpe a busca
5. Todos reaparecem
```

### 7. Teste Envio do Formulário
```
1. Adicione 2+ colaboradores
2. Se origem LIVRE: adicione 1 procedimento
3. Preencha data prevista
4. Clique em Salvar
5. Se falta algo obrigatório: verá aviso
6. Se tudo OK: formulário envia e planejamento é criado
```

### 8. Teste Validação
```
Teste 1: Tentar enviar SEM colaboradores
- Resultado: Alerta "Por favor, selecione pelo menos um colaborador!"
- Formulário NÃO é enviado

Teste 2: Tentar enviar com origem LIVRE SEM procedimento
- Resultado: Alerta "Por favor, selecione um procedimento"
- Formulário NÃO é enviado

Teste 3: Enviar com tudo preenchido
- Resultado: Formulário envia com sucesso
```

## 🔍 Verificar no Browser Console

Abra DevTools (F12) e no Console digite:

```javascript
// Ver colaboradores selecionados
console.log(colaboradoresSelecionados);

// Ver procedimentos selecionados
console.log(procedimentosSelecionados);

// Ver valores dos hidden inputs
console.log(document.getElementById('colaboradores_hidden').value);
console.log(document.getElementById('procedimento_hidden').value);
```

## 📊 O que Deve Aparecer

Depois que adicionar colaboradores e procedimento:

```javascript
colaboradoresSelecionados = {
    "1": "João Silva",
    "2": "Maria Santos"
}

procedimentosSelecionados = {
    "5": "PROC_001 - Procedimento de Calibração"
}

// Hidden inputs
colaboradores_hidden.value = "1,2"
procedimento_hidden.value = "5"
```

## ✨ Recursos Visíveis

| Feature | Onde Ver |
|---------|----------|
| Modal colaboradores | Botão "Adicionar Colaborador" → Modal |
| Modal procedimento | Botão "Adicionar Procedimento" → Modal (LIVRE) |
| Lista colaboradores | Sob "Colaboradores *" com nomes + ✕ |
| Lista procedimento | Sob "Procedimento" com código + nome + ✕ |
| Busca colaborador | Campo "Buscar colaborador..." no modal |
| Busca procedimento | Campo "Buscar procedimento..." no modal |
| Validação | Alerta ao enviar sem seleções obrigatórias |

## 🐛 Se Algo Não Funcionar

1. **Modal não abre**
   - Verifique se Bootstrap 5 está carregado
   - Verifique console para erros JavaScript

2. **Busca não funciona**
   - Abra console (F12)
   - Verifique se não há erros
   - Teste digitando no campo de busca

3. **Items não aparecem na lista após adicionar**
   - Verifique se há dados no banco (colaboradores/procedimentos)
   - Veja console para erros

4. **Form não valida**
   - Verifique se JavaScript está rodando (console)
   - Teste adicionar pelo menos 1 colaborador
   - Se origem LIVRE, teste adicionar procedimento

## 📱 Testar em Mobile

1. Abra em celular: http://localhost:8000/procedures/planejamentos/novo/
2. Verifique se layout é responsivo
3. Teste modais em tela pequena
4. Verifique se busca funciona em touch

## ✅ Checklist Completo

- [ ] Formulário carrega sem erros
- [ ] Modal colaboradores abre e fecha
- [ ] Modal procedimento abre e fecha
- [ ] Busca nos modals funciona
- [ ] Posso adicionar colaboradores
- [ ] Posso remover colaboradores
- [ ] Lista mostra seleções corretamente
- [ ] Posso adicionar procedimento
- [ ] Validação bloqueia submit sem colaboradores
- [ ] Validação bloqueia submit sem procedimento (LIVRE)
- [ ] Formulário envia corretamente quando completo
- [ ] Planejamento é criado com as seleções

---

**Quando tudo estiver funcionando**: Abra uma issue ou comente se encontrar bugs! 🎉
