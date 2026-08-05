# Implementação: Atualização em Massa de Datas de Calibração

## Resumo
Implementação de funcionalidade para atualizar em massa as datas de próximas calibrações de todos os instrumentos do sistema com um único clique.

## Problema Resolvido
Anteriormente, o sistema só permitia atualizar as datas de calibração de um instrumento por vez através do botão "Atualizar Datas" individual. Para uma operação administrativa comum (sincronizar todas as datas após correção de frequências), era necessário:
1. Entrar em cada instrumento individualmente
2. Clicar em "Atualizar Datas"
3. Confirmar a ação
4. Repetir centenas de vezes para grandes inventários

## Solução Implementada

### 1. Frontend - Dashboard da Metrologia
**Arquivo:** `metrologia/templates/metrologia/dashboard.html`

#### Botão adicionado (linhas ~65-70):
```html
<button class="btn btn-outline-info btn-sm shadow-sm" 
        title="Atualizar todas as datas de calibração" 
        onclick="atualizarTodasDatas()">
    <i class="bi bi-arrow-clockwise"></i> Atualizar Datas
</button>
```

#### Função JavaScript adicionada (linhas ~640-680):
```javascript
function atualizarTodasDatas() {
    if (!confirm('Deseja atualizar as datas de próximas calibrações para TODOS os instrumentos?')) {
        return;
    }
    
    const btn = event.target.closest('button');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Atualizando...';
    
    fetch('{% url "metrologia:atualizar_todas_datas_calibracao" %}', {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`✅ Sucesso!\n\n${data.message}`);
            location.reload();
        } else {
            alert(`❌ Erro:\n\n${data.message}`);
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    })
    .catch(error => {
        alert(`❌ Erro na requisição:\n\n${error.message}`);
        btn.disabled = false;
        btn.innerHTML = originalText;
    });
}
```

**Funcionalidades:**
- Confirmação do usuário antes de executar
- Spinner visual durante o processamento
- CSRF token handling automático
- Tratamento de erros com mensagens claras
- Recarga automática da página após sucesso

### 2. Backend - View em QMS
**Arquivo:** `qms/views.py` (linhas ~2507-2593)

#### Função implementada:
```python
@login_required
@require_POST
def atualizar_todas_datas_calibracao_view(request):
    """Atualiza em massa as datas de próximas calibrações de todos os instrumentos."""
    from dateutil.relativedelta import relativedelta
    
    try:
        atualizado_count = 0
        erro_count = 0
        
        # Buscar todos os instrumentos ativos
        instrumentos = Instrumento.objects.filter(ativo=True)
        
        for instrumento in instrumentos:
            try:
                # Buscar o histórico mais recente
                ultimo_historico = HistoricoCalibracao.objects.filter(
                    instrumento=instrumento
                ).order_by('-data_calibracao').first()
                
                if not ultimo_historico:
                    continue
                
                # Atualizar data da última calibração
                instrumento.data_ultima_calibracao = ultimo_historico.data_calibracao
                
                # Recalcular próxima calibração baseado na frequência do instrumento
                meses = None
                
                if instrumento.frequencia_meses:
                    meses = instrumento.frequencia_meses
                elif instrumento.categoria and instrumento.categoria.frequencia_calibracao_meses:
                    meses = instrumento.categoria.frequencia_calibracao_meses
                
                if meses:
                    instrumento.data_proxima_calibracao = (
                        ultimo_historico.data_calibracao + relativedelta(months=meses)
                    )
                else:
                    instrumento.data_proxima_calibracao = (
                        ultimo_historico.proxima_calibracao 
                        if hasattr(ultimo_historico, 'proxima_calibracao') 
                        else None
                    )
                
                instrumento.save(update_fields=['data_ultima_calibracao', 'data_proxima_calibracao'])
                atualizado_count += 1
                
            except Exception as e:
                logger.error(f"Erro ao atualizar instrumento {instrumento.id}: {str(e)}")
                erro_count += 1
        
        message = f'Datas de calibração atualizadas para {atualizado_count} instrumentos.'
        if erro_count > 0:
            message += f' {erro_count} erros encontrados.'
        
        logger.info(f"Atualização em massa concluída: {atualizado_count} sucesso, {erro_count} erros")
        
        return JsonResponse({
            'success': True,
            'message': message,
            'atualizado': atualizado_count,
            'erros': erro_count
        })
        
    except Exception as e:
        logger.error(f"Erro ao atualizar datas em massa: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Erro ao atualizar datas: {str(e)}'
        }, status=400)
```

**Funcionalidades:**
- Processa apenas instrumentos ativos (`ativo=True`)
- Usa o histórico mais recente (`HistoricoCalibracao`)
- Prioriza frequência do instrumento sobre categoria
- Calcula próxima calibração com `relativedelta(months=frequencia)`
- Usa `update_fields` para otimizar queries
- Retorna JSON com estatísticas
- Logging detalhado de sucesso e erros
- Tratamento robusto de exceções

### 3. Roteamento - URL
**Arquivo:** `metrologia/urls.py` (linha ~88)

```python
path('api/atualizar-todas-datas/', 
     qms_views.atualizar_todas_datas_calibracao_view, 
     name='atualizar_todas_datas_calibracao'),
```

## Fluxo de Execução

```
1. Usuário clica botão "Atualizar Datas"
   ↓
2. JavaScript: Exibe confirmação
   ↓
3. Se confirmado: Fetch POST para /metrologia/api/atualizar-todas-datas/
   ↓
4. CSRF token incluído automaticamente
   ↓
5. View recebe requisição
   ↓
6. Itera sobre todos os Instrumento.objects.filter(ativo=True)
   ↓
7. Para cada instrumento:
   - Busca último HistoricoCalibracao
   - Lê frequência_meses do instrumento
   - Se vazio, usa frequência_calibracao_meses da categoria
   - Calcula: data_proxima = data_ultima + relativedelta(months=frequencia)
   - Salva instrumento
   ↓
8. Retorna JSON com { success: true, message: "X updated", atualizado: X, erros: Y }
   ↓
9. JavaScript: Exibe mensagem e recarrega página
```

## Tratamento de Frequências

A função respira o algoritmo de frequência corrigido implementado em commits anteriores:

| Cenário | Frequência Usada |
|---------|-----------------|
| Instrumento tem `frequencia_meses` | `instrumento.frequencia_meses` |
| Instrumento não tem, categoria tem | `categoria.frequencia_calibracao_meses` |
| Nenhum tem frequência definida | `None` (campo fica vazio/null) |

Exemplo:
- Instrumento: calibrado 03/11/2024, frequência 12 meses
- Resultado: próxima calibração = 03/11/2025

## Segurança e Performance

### Segurança:
- `@login_required`: Apenas usuários autenticados
- `@require_POST`: Protege contra GET requests
- CSRF token validation automática
- Logging de operações para auditoria

### Performance:
- `ativo=True` filter: Pula instrumentos inativos
- `order_by('-data_calibracao')`: Índice de banco de dados
- `.first()`: Retorna apenas um registro
- `update_fields`: Atualiza apenas campos modificados

## Casos de Uso

1. **Sincronização pós-mudança de frequência:**
   - Alterar frequência de categoria
   - Clicar "Atualizar Datas"
   - Todos os instrumentos recalculam próxima calibração

2. **Correção de dados históricos:**
   - Importar novos históricos
   - Clicar "Atualizar Datas"
   - Sistema recalcula com base em registros mais recentes

3. **Manutenção preventiva:**
   - Garantir consistência entre históricos e datas calculadas
   - Operação única em vez de centenas de cliques

## Commit
- **Hash**: d921a36
- **Mensagem**: "feat: Adicionar atualização em massa de datas de calibração"
- **Data**: Implementado conforme parte da sessão de otimizações

## Validação

✅ Django check passou sem erros
✅ URL criada e acessível em `/metrologia/api/atualizar-todas-datas/`
✅ Função decorada corretamente com `@login_required @require_POST`
✅ Sintaxe Python validada com `py_compile`
✅ Imports corretos (todos já presentes no arquivo)

## Próximos Passos (Opcional)

1. **Testes de integração:** Criar fixtures de dados de teste
2. **Documentação do usuário:** Adicionar ao manual de operações
3. **Auditoria:** Registrar quem executou a operação em timestamp
4. **Throttling:** Adicionar rate limiting se necessário
5. **Preview:** Opção de visualizar mudanças antes de confirmar
