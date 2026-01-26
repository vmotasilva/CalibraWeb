# 🚀 GUIA RÁPIDO - Filtros e Multi-Select v2.0

## 5 Segundos para Entender

**Antes:** Adicionar 10 procedimentos = 50 cliques + 5 minutos  
**Agora:** Adicionar 10 procedimentos = 3 cliques + 10 segundos

---

## 3 Passos Rápidos

### 1️⃣ Filtrar
```
Busca:   "ISO" ou "DEX.002"
Matriz:  "QED" (opcional)
Subárea: "RH" (opcional)

↓ Lista atualiza automaticamente
```

### 2️⃣ Selecionar
```
☑ Marque os checkboxes
☑ Ou clique "Selecionar Todos"

↓ Contador e lista atualizam
```

### 3️⃣ Adicionar
```
Configurar ordem e obrigatoriedade
Clicar: "Adicionar Selecionados"

✅ PRONTO! Vários procedimentos adicionados em 1 clique!
```

---

## Campos de Filtro

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| **Busca** | Procura em código, nome ou descrição | ISO 9001, DEX.002 |
| **Matriz** | Filtra por matriz/grupo principal | QED, FOR, EST |
| **Subgrupo** | Filtra por subárea | RH, Compliance, Legal |

**Todos funcionam juntos!**  
Matriz + Subgrupo + Busca = Filtro preciso

---

## Botões Importantes

| Botão | O Que Faz |
|-------|-----------|
| **+ Adicionar Procedimento** | Abre modal com filtros |
| **Selecionar Todos** | Marca todos os filtrados |
| **Desselecionar Todos** | Desmarca todos |
| **Adicionar Selecionados** | Adiciona múltiplos de uma vez |

---

## Exemplo Prático

### Adicionar todos os procedimentos de ISO

```
PASSO 1: Abrir
└─> Clique "+ Adicionar Procedimento"

PASSO 2: Buscar
└─> Digite "ISO" na busca
└─> Ver 12 resultados aparecerem

PASSO 3: Selecionar
└─> Clique "Selecionar Todos"
└─> Veja: "12 procedimentos selecionados"

PASSO 4: Configurar
└─> Ordem: 1 (incrementa: 1, 2, 3...)
└─> Obrigatório: ☑ (todos serão obrigatórios)

PASSO 5: Adicionar
└─> Clique "Adicionar Selecionados"
└─> ✅ Resultado: 12 procedimentos adicionados!

TEMPO TOTAL: 20 segundos
ANTIGO: 5 minutos
```

---

## Resultado Esperado

Depois de clicar "Adicionar Selecionados":

```
✅ Sucesso (Verde)
"12 procedimento(s) adicionado(s): 
DEX.002, DEX.003, DEX.004, ..."

⚠️  Aviso (Amarelo)
"2 procedimento(s) já estava(m) associado(s): 
DEX.001, DEX.005"

❌ Erro (Vermelho)
"Erro ao adicionar: Procedimento ID 99999 não encontrado"
```

---

## Dicas Práticas

### Filtro Rápido de Matriz
```
1. Abrir modal
2. Selecionar Matriz: "QED"
3. Clicar "Selecionar Todos"
4. Todos os procedimentos da QED selecionados!
```

### Busca Específica
```
1. Digitar código exato: "DEX.002"
2. Marca o checkbox do resultado
3. Clicar "Adicionar Selecionados"
4. Procedimento adicionado sozinho
```

### Combinação de Filtros
```
Matriz: "QED" + Subárea: "RH" + Busca: "treinamento"
= Só mostra procedimentos que combinam TUDO!
```

---

## Botões Auxiliares

### Selecionar Todos
✅ Marca todos os procedimentos na lista atual  
✅ Respeita os filtros aplicados  
✅ Útil para adicionar grupos inteiros

### Desselecionar Todos
❌ Desmarca todos  
❌ Útil se errou na seleção

---

## Verificação Automática

Sistema verifica automaticamente:

✅ Procedimento já está associado?  
   → Avisa em amarelo, não adiciona duplicata

✅ Procedimento não existe?  
   → Avisa em vermelho, não trava

✅ Faltaram campos obrigatórios?  
   → Botão "Adicionar" fica desabilitado até selecionar

---

## Performance

| Ação | Tempo |
|------|-------|
| Abrir modal | < 1 segundo |
| Digitar busca | Instantâneo (sem F5) |
| Selecionar/deselecionar | Instantâneo |
| Adicionar 10 procedimentos | < 2 segundos |
| Atualizar tabela | < 1 segundo |

---

## Troubleshooting

**P: Modal abre mas não mostra procedimentos**
```
R: Aguarde 1 segundo para carregar
   Se continuar: F5 na página
```

**P: Filtro não funciona**
```
R: Verifique se digitou corretamente
   Tente sem usar acentos
   Limpe o campo de busca
```

**P: Procedimento não aparece no dropdown**
```
R: Já está associado? 
   Sistema filtra automaticamente procedimentos já adicionados
   Tente desassociar primeiro
```

---

## Keyboard Shortcuts

| Tecla | Ação |
|-------|------|
| `Tab` | Navegar entre campos |
| `Enter` | Adicionar (quando selecionado) |
| `Esc` | Fechar modal |

---

## 🎯 Resumo das Melhorias

| Recurso | Novo? |
|---------|-------|
| Buscar por código/nome | ✅ SIM |
| Filtro por matriz | ✅ SIM |
| Filtro por subgrupo | ✅ SIM |
| Multi-select | ✅ SIM |
| Selecionar/Desselecionar todos | ✅ SIM |
| Adicionar múltiplos em lote | ✅ SIM |
| Incremento automático de ordem | ✅ SIM |
| Validação de duplicatas | ✅ (Melhorado) |

---

## 📚 Mais Detalhes

Para documentação completa, veja:  
👉 `ATUALIZACAO_FILTROS_MULTISELECT.md`

---

**Versão:** 2.0  
**Data:** 29/12/2025  
**Status:** ✅ Pronto para usar!

Aproveite! 🚀
