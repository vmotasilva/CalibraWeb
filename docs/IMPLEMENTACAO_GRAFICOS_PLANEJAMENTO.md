# Implementação de Gráficos de Planejamento de Treinamentos

## Data de Implementação
- **Commit**: `12fd0c3`
- **Data**: [data atual]
- **Deploy**: Railway Production (https://calibraweb.up.railway.app/)

## Resumo da Funcionalidade

Foram adicionados **2 novos gráficos** ao Dashboard de Treinamentos para visualização de dados de **Planejamento de Treinamentos** com análise de status em 4 categorias.

### Gráfico 1: Planejados por Setor e Turno
- **Eixo Y**: Combinações de setor + turno (top 15)
- **Eixo X**: Quantidade de treinamentos
- **Tipo**: Barra horizontal empilhada
- **Categorias de Status**:
  - 🟢 **No Prazo** (Verde) - Treinamentos dentro do cronograma
  - 🔴 **Fora do Prazo** (Vermelho) - Treinamentos atrasados
  - ⚫ **Cancelados** (Cinza) - Treinamentos cancelados
  - 🔵 **Concluídos** (Azul) - Treinamentos realizados

### Gráfico 2: Planejados por Instrutor
- **Eixo Y**: Nomes dos instrutores (top 15)
- **Eixo X**: Quantidade de treinamentos
- **Tipo**: Barra horizontal empilhada
- **Categorias de Status**: Mesmas do Gráfico 1

### Seletor de Período
- **Localização**: Acima dos gráficos (lado direito)
- **Opções**:
  - Últimos 3 meses (padrão)
  - Últimos 6 meses
  - Últimos 12 meses
- **Funcionamento**: Ao selecionar, a página recarrega com o filtro `periodo_planejamento` no GET

## Arquivos Modificados

### 1. `training/views/views.py`
**Mudanças anteriores (commit c3d306e):**
- Adicionadas importações: `from dateutil.relativedelta import relativedelta`, `from datetime import timedelta`
- Adicionada função de cálculo de dados de planejamento (linhas ~631-735)
- Calcula agrupamentos por (setor, turno) e por instrutor
- Categoriza cada treinamento por status: no_prazo, fora_prazo, cancelados, concluidos
- Retorna top 15 de cada grupo
- Adiciona contexto: `planejamentos_setor_turno`, `planejamentos_instrutor`, `periodo_planejamento`

**Lógica de Cálculo:**
```python
periodo_meses = int(request.GET.get('periodo_planejamento', 3))
data_inicio = date.today() - relativedelta(months=periodo_meses)

# Itera sobre PlanejamentoTreinamento.objects.filter(data_prevista__gte=data_inicio)
# Agrupa por (setor, turno) ou instrutor
# Categoriza por status (PLANEJADO vs data_prevista) em 4 categorias

# Retorna lista com estrutura:
# {
#   'nome': 'Setor X - Turno Y',
#   'no_prazo': 10,
#   'fora_prazo': 5,
#   'cancelados': 2,
#   'concluidos': 8
# }
```

### 2. `procedures/templates/procedures/dashboard_treinamentos.html`

**Novas Seções Adicionadas:**

#### 2.1 Seletor de Período (linhas ~340-350)
```html
<div style="width: 200px;">
    <label for="periodoGraph" class="form-label mb-2 small fw-bold">Período:</label>
    <select id="periodoGraph" class="form-select form-select-sm">
        <option value="3" {% if periodo_planejamento == 3 %}selected{% endif %}>Últimos 3 meses</option>
        <option value="6" {% if periodo_planejamento == 6 %}selected{% endif %}>Últimos 6 meses</option>
        <option value="12" {% if periodo_planejamento == 12 %}selected{% endif %}>Últimos 12 meses</option>
    </select>
</div>
```

#### 2.2 Contêiner de Gráficos (linhas ~355-385)
- Card para Gráfico 1: "Planejados por Setor e Turno" (canvas id: `chartPlanejamentoSetorTurno`)
- Card para Gráfico 2: "Planejados por Instrutor" (canvas id: `chartPlanejamentoInstrutor`)
- Ambos em layout 2 colunas (col-lg-6)

#### 2.3 Função JavaScript `initPlanejamentoCharts()` (linhas ~710-835)
```javascript
// Renderiza os 2 gráficos de planejamento
// Dados: dadosPlanejamento.planejamentos_setor_turno e .planejamentos_instrutor
// Cores: Verde, Vermelho, Cinza, Azul para os 4 status
// Tipo: Barra horizontal empilhada
// Escala: Stacked para visualizar o total
```

#### 2.4 Event Listener do Período (linhas ~896-900)
```javascript
document.getElementById('periodoGraph').addEventListener('change', function() {
    const periodo = this.value;
    const url = window.location.pathname + '?periodo_planejamento=' + periodo;
    window.location.href = url;
});
```

#### 2.5 Inicialização (linhas ~904-910)
- Adicionada chamada a `initPlanejamentoCharts()` no `DOMContentLoaded`
- Chama com 500ms de delay após `initCharts()`

## Fluxo de Funcionamento

```
┌─────────────────────────────────────────────────┐
│   1. Carregamento do Dashboard                  │
│   GET /treinamentos/?periodo_planejamento=3    │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│   2. Backend (dashboard_treinamentos_view)      │
│   - Processa periodo_planejamento               │
│   - Calcula agrupamentos de dados               │
│   - Adiciona ao contexto:                       │
│     * planejamentos_setor_turno                 │
│     * planejamentos_instrutor                   │
│     * periodo_planejamento                      │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│   3. Template Rendering                         │
│   - Exibe seletor de período                    │
│   - Injeta dados em dadosPlanejamento           │
│   - Renderiza canvas elements                  │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│   4. JavaScript (DOMContentLoaded)              │
│   - Chama initPlanejamentoCharts()              │
│   - Cria 2 instâncias Chart.js                  │
│   - Renderiza gráficos com dados                │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│   5. Interação Usuário                          │
│   - Usuário muda período no selector            │
│   - Event listener dispara                      │
│   - Navega para ?periodo_planejamento=X         │
│   - Volta ao passo 2                            │
└─────────────────────────────────────────────────┘
```

## Dados Utilizados

**Modelo**: `PlanejamentoTreinamento`

**Campos Utilizados:**
- `titulo`: Nome do planejamento
- `data_prevista`: Data prevista para realizção
- `data_realizada`: Data de realização (se concluído)
- `status`: PLANEJADO | CONFIRMADO | REALIZADO | CANCELADO
- `instrutor` (FK): Instrutor responsável
- `colaboradores` (M2M): Colaboradores envolvidos
  - Relacionado a `Colaborador.setor` e `Colaborador.turno`

**Filtros Aplicados:**
- Apenas treinamentos com `data_prevista >= hoje - N meses`
- Ordenação: Top 15 por total de treinamentos

**Categorização de Status:**
1. **no_prazo**: `status != 'CANCELADO' AND data_prevista >= hoje`
2. **fora_prazo**: `status != 'CANCELADO' AND data_prevista < hoje`
3. **cancelados**: `status == 'CANCELADO'`
4. **concluidos**: `status == 'REALIZADO'`

## Cores Utilizadas

| Status | Cor | Código RGB |
|--------|-----|-----------|
| No Prazo | Verde | rgba(40, 167, 69, 0.8) |
| Fora do Prazo | Vermelho | rgba(248, 113, 113, 0.8) |
| Cancelados | Cinza | rgba(108, 117, 125, 0.8) |
| Concluídos | Azul | rgba(23, 162, 184, 0.8) |

## Testes Recomendados

- [ ] Carregamento da dashboard com 3 meses
- [ ] Mudança de período para 6 meses
- [ ] Mudança de período para 12 meses
- [ ] Verificar se top 15 está sendo respeitado
- [ ] Verificar cores das categorias de status
- [ ] Verificar labels no gráfico por setor e turno
- [ ] Verificar labels no gráfico por instrutor
- [ ] Performance com grande volume de dados
- [ ] Responsividade em diferentes tamanhos de tela

## Deploy Status

✅ **Deployado em Produção**
- Commit: `12fd0c3`
- Branch: `main`
- Plataforma: Railway.app
- URL: https://calibraweb.up.railway.app/
- Status: Live

## Notas Adicionais

1. **Compatibilidade com Filtros Existentes**: Os gráficos de planejamento são independentes dos filtros de setor/turno/líderes. Eles mostram sempre o panorama geral do planejamento.

2. **Performance**: Com a limitação de top 15 itens, a performance do frontend é garantida mesmo com muitos dados.

3. **Atualização Dinâmica**: Os gráficos são recalculados a cada mudança de período, sempre trazendo dados frescos do backend.

4. **Escalabilidade**: A estrutura permite fácil adição de novos gráficos no futuro (ex: por grupo/subgrupo de treinamento).

## Próximos Passos Possíveis

1. Adicionar filtros aos gráficos de planejamento (por agora são apenas por período)
2. Exportar dados dos gráficos em CSV/PDF
3. Comparação de períodos (mostrar variação)
4. Integração com alertas para atrasos
5. Dashboard em tempo real com WebSockets
