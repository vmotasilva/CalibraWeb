# Deploy - Modal Popup de Avaliação de Habilidades

## Resumo das Mudanças

### Funcionalidades Implementadas

1. **Modal Popup Interativo**
   - Clique em qualquer badge de avaliação abre um modal sem sair da matriz
   - Carregamento automático de dados da avaliação existente
   - Design responsivo com cards visuais para seleção de nível

2. **APIs AJAX Criadas**
   - `GET /procedures/api/avaliacoes/<matriz>/<colab>/<disc>/` - Obter dados
   - `POST /procedures/api/avaliacoes/<matriz>/<colab>/<disc>/salvar/` - Salvar avaliação

3. **Melhorias de UX**
   - Seleção de nível com cards interativos (N/A, 0, 1, 2, 3)
   - Campo de data com valor padrão de hoje
   - Campo de observações opcional
   - Toast de feedback visual após salvar
   - Atualização em tempo real do badge na matriz

### Arquivos Modificados

1. **procedures/templates/procedures/matriz_avaliacao.html**
   - Alterado links para usar JavaScript ao invés de navegação direta
   - Adicionado modal de avaliação com template HTML
   - Adicionado CSS para cards do modal
   - Adicionado JavaScript para controle do modal e AJAX

2. **procedures/views/avaliacoes_views.py**
   - Adicionada view `obter_avaliacao_api()` - GET
   - Adicionada view `salvar_avaliacao_api()` - POST
   - Melhorado tratamento de erros com logging
   - Conversão correta de tipos (data, setor)

3. **procedures/urls.py**
   - Adicionadas rotas para as novas APIs
   - URLs: `/procedures/api/avaliacoes/<...>/` e `/salvar/`

### Correções de Bugs

1. **JSON Serialization**
   - Campo `setor` era um objeto Setor, agora convertido para string

2. **Date Handling**
   - Data agora corretamente convertida de string YYYY-MM-DD para date object

3. **CSRF Token**
   - Token agora obtido diretamente do template Django (`{{ csrf_token }}`)
   - Mais seguro e confiável que obter via cookie

## Status de Deployment

✅ **Pronto para Produção**

- Commit feito: `a6ab60b`
- Branch: `main`
- Enviado para GitHub: `vmotasilva/CalibraWeb`
- Render.com será notificado automaticamente ao detectar push em `main`

## Passos de Deploy Manual (se necessário)

1. **Verificar conexão com banco**
   ```bash
   python manage.py check --database default
   ```

2. **Executar migrações**
   ```bash
   python manage.py migrate --noinput
   ```

3. **Coletar arquivos estáticos**
   ```bash
   python manage.py collectstatic --noinput --clear
   ```

4. **Reiniciar aplicação**
   - No Render.com: Menu → Manual Deploy (ou push em main)

## Testes Recomendados em Produção

1. Abrir página de avaliações
2. Clicar em um badge (vazio ou preenchido)
3. Verificar carregamento correto dos dados
4. Selecionar nível e salvar
5. Confirmar atualização do badge sem recarregar página

## Rollback (se necessário)

```bash
git revert a6ab60b
git push origin main
```

Render.com detectará a mudança e redeployará automaticamente.
