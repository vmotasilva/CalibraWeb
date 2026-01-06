# 📋 Guia de Uso: Mapear Placeholders no PDF

## O que é essa tela?

A tela **"Mapear Placeholders"** permite que você associe os campos de dados do seu sistema com os placeholders (variáveis) que aparecem no seu PDF de Lista de Presença.

Por exemplo: O PDF tem um local onde escreve `{{titulo}}` - você precisa dizer ao sistema que esse espaço deve ser preenchido com o "Título do Procedimento" do banco de dados.

---

## 🎯 Como Usar

### Método 1: Clique Direto no PDF (Mais Fácil) ⭐

Esta é a **forma mais intuitiva e recomendada**:

#### Passo 1: Ativar Modo de Clique
1. Procure pelo **ícone de crosshair** (⊕) na barra de controles do PDF
2. Clique nele para ativar o "modo de clique"
3. Seu **cursor vai mudar para um crosshair** quando passar sobre o PDF

#### Passo 2: Clicar no PDF
1. Procure no PDF pelo placeholder que deseja mapear (ex: `{{titulo}}`)
2. **Clique exatamente sobre o placeholder** no PDF
3. Um **popup com botões vai aparecer** mostrando todas as opções

#### Passo 3: Selecionar o Campo
1. No popup que apareceu, clique no campo que corresponde àquele placeholder
2. Por exemplo, se clicou em `{{titulo}}` no PDF, clique em "Título do Procedimento"

#### Passo 4: Repetir
1. O placeholder vai ficar **destacado em amarelo** na lista à direita
2. Repita os passos 2-3 para cada placeholder do PDF

### Método 2: Usar o Painel Direito

Se preferir uma abordagem mais tradicional:

1. Procure na lista **à direita** pelo placeholder que deseja mapear
2. **Clique no placeholder** na lista
3. O PDF vai se mover para destacar aquele placeholder (efeito glow)
4. Clique na caixa **dropdown** para selecionar qual campo do seu sistema corresponde

---

## 🔍 Funcionalidades Extras

### 🔎 Buscar no PDF
- Use a **caixa de busca** na barra de controles do PDF
- Digite o nome do placeholder (ex: `data`)
- O PDF vai destacar a página que contém esse termo

### 📄 Navegar no PDF
- Use os **botões de seta** para ir para a página anterior/próxima
- Ou **digite o número da página** na caixa de entrada
- O programa mostra quantas páginas tem (ex: "1 / 5")

### 📤 Carregar/Trocar PDF
- Clique no **ícone de upload** para carregar um novo PDF
- Ou clique no **ícone de lixeira** para remover o PDF atual
- A página vai recarregar com o novo PDF

---

## ✅ Status da Mapeamento

No topo da página, você vê:

| Badge | Significado |
|-------|------------|
| **6 Placeholders** | Total de campos a mapear |
| **X Mapeados** | Quantos já foram associados |
| **Y Pendentes** | Quantos ainda faltam fazer |

Uma **barra de progresso** também mostra visualmente o avanço.

---

## 📝 Campos Disponíveis Para Mapear

Esses são os placeholders que podem existir no seu PDF:

- `{{titulo}}` - Título do procedimento
- `{{facilitador}}` - Nome de quem facilita/ministra
- `{{data}}` - Data do procedimento
- `{{hora_inicio}}` - Horário de início
- `{{carga_horaria}}` - Carga horária total
- `{{procedimentos}}` - Nome ou descrição dos procedimentos

---

## 💾 Salvando Seu Mapeamento

1. Após associar todos os campos, clique no botão **"Salvar Mapeamento"** no final da página
2. Uma mensagem de confirmação vai aparecer
3. Seus mapeamentos são salvos no sistema
4. Agora seus PDFs de Lista de Presença vão ser preenchidos automaticamente com os dados!

---

## ⚠️ Dicas Importantes

1. **Não é obrigatório mapear todos os campos** - Se seu PDF não tiver um placeholder, deixe em branco
2. **Pode mudar de ideia** - Volte para essa tela e mude as associações quando quiser
3. **Um campo para cada placeholder** - Não é possível usar o mesmo campo em dois placeholders diferentes
4. **Clique com cuidado** - Certifique-se de clicar exatamente no placeholder desejado

---

## 🆘 Problemas Comuns

### O PDF não carrega
- Certifique-se de que o arquivo PDF foi carregado corretamente
- Tente carregar novamente (ícone de upload)
- O arquivo deve ser um PDF válido

### O popup não aparece ao clicar
- Verifique se o **modo de clique está ativo** (ícone de crosshair deve estar visível)
- Tente clicar mais precisamente sobre o texto do placeholder
- Se ainda não funcionar, use o **Método 2** (painel direito)

### Não consigo encontrar um placeholder
- Use a **busca do PDF** para encontrar o placeholder
- Verifique se digitou o nome certo (ex: `titulo` em vez de `titulo`)
- Procure em todas as páginas do PDF

### Esqueci de salvar
- Não se preocupe! Clique no botão **"Salvar Mapeamento"** antes de sair
- Se sair sem salvar, as mudanças serão perdidas

---

## 🎬 Fluxo Visual Resumido

```
┌─────────────────────────────────────────────────────┐
│ 1. Ativar Modo Clique (⊕)                           │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 2. Clicar no Placeholder no PDF                     │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 3. Popup Aparece com Opções                         │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 4. Selecionar Campo Correspondente                  │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 5. Placeholder Fica Destacado em Amarelo            │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 6. Repetir para Cada Placeholder                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 7. Clicar em "Salvar Mapeamento"                    │
└─────────────────────────────────────────────────────┘
```

---

## ✨ Dicas Pro

- **Dica 1**: Se o seu PDF está muito pequeno, use o zoom do navegador (Ctrl + +)
- **Dica 2**: Se tem muitos placeholders, comece pelos que aparecem no topo
- **Dica 3**: Você pode revisar e mudar os mapeamentos quantas vezes quiser
- **Dica 4**: O sistema não permite o mesmo campo ser mapeado para dois placeholders diferentes

---

Pronto! Agora você já sabe como usar. Qualquer dúvida, consulte este guia novamente! 🎉
