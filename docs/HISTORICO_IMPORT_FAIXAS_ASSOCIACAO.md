# 📋 Importação de Histórico - Associação de Faixas Existentes

**Data:** 16 de Janeiro de 2026  
**Commit:** `45d2e12` - refactor: import de histórico associa faixas existentes sem criar novas  
**Status:** ✅ Deployed para produção

## 🎯 Objetivo

Modificar o fluxo de importação de histórico de calibração para:
- **NÃO criar** novas faixas de medição durante a importação
- **ASSOCIAR automaticamente** as faixas já existentes do instrumento
- **VALIDAR** os dados de calibração contra as faixas existentes

## 📊 Fluxo Antes vs Depois

### ❌ ANTES (Comportamento Anterior)

```
Importação de Histórico
  ├─ Cria/atualiza HistoricoCalibracao
  ├─ Tenta criar novas FaixaMedicao (se não existirem)
  └─ Associa ResultadoFaixaCalibracao
```

**Problema:** Poderia criar faixas duplicadas ou incorretas

### ✅ DEPOIS (Novo Comportamento)

```
Importação de Histórico
  ├─ Cria/atualiza HistoricoCalibracao
  ├─ Busca TODAS as FaixaMedicao existentes do instrumento
  ├─ Para cada faixa existente:
  │  └─ Cria/atualiza ResultadoFaixaCalibracao com:
  │     ├─ Referência para a faixa existente (faixa_id)
  │     ├─ Dados do histórico (erro, incerteza, tolerância)
  │     └─ Resultado é calculado automaticamente
  └─ Atualiza datas do instrumento
```

**Benefícios:**
- ✅ Não cria faixas duplicadas
- ✅ Usa apenas faixas válidas e já cadastradas
- ✅ Garante consistência de dados
- ✅ Permite validação posterior

## 🔧 Detalhes Técnicos

### Arquivo Modificado: `qms/tasks.py`

**Função:** `import_historico_task(job_id, filepath)`

**Mudança Principal:** Após criar/atualizar `HistoricoCalibracao`, o sistema agora:

```python
# Buscar todas as faixas existentes do instrumento
faixas_existentes = FaixaMedicao.objects.filter(instrumento=inst).order_by('valor_minimo')

# Para cada faixa existente, criar/atualizar ResultadoFaixaCalibracao
for faixa in faixas_existentes:
    resultado, _ = ResultadoFaixaCalibracao.objects.update_or_create(
        historico=obj,
        faixa=faixa,
        defaults={
            'valor_minimo': faixa.valor_minimo,
            'valor_maximo': faixa.valor_maximo,
            'erro': float(erro),
            'incerteza': float(inc),
            'tolerancia': float(tol),
        }
    )
```

### Mensagem de Importação Atualizada

**Antes:**
```
Historico: 5 new, 2 updated, 1 ignored (missing TAG/date)
```

**Depois:**
```
Historico: 5 new, 2 updated, 1 ignored (missing TAG/date). 
Faixas existentes foram associadas para validação.
```

## 📋 Pré-requisitos para a Importação Funcionar

**IMPORTANTE:** As faixas de medição devem ser criadas ANTES da importação de histórico!

### Fluxo Correto:

1. **Importar Instrumentos** (cria as faixas)
   ```
   /metrologia/imp-inst/ → Upload Excel com instrumentos e faixas
   ```

2. **Importar Histórico** (associa aos históricos)
   ```
   /metrologia/imp-hist/ → Upload Excel com históricos
   ```

### Fluxo Incorreto ❌

```
❌ Importar Histórico
   └─ Sem faixas existentes
      └─ Nenhuma validação será feita
```

## 🚀 Deployment

- **Commit:** 45d2e12
- **Branch:** main
- **Ambiente:** Production (Railway)
- **Webhook:** Automático disparado
- **ETA:** 2-3 minutos

## 📝 Exemplos de Uso

### Template de Importação de Histórico

O template continua o mesmo, com as colunas:

| TAG | DATA CALIBRAÇÃO | DATA APROVAÇÃO | N CERTIFICADO | ERRO ENCONTRADO | INCERTEZA | TOLERANCIA PROCESSO | RBC | RESULTADO |
|-----|-----------------|-----------------|---------------|-----------------|-----------|-------------------|-----|-----------|
| INS-001 | 01/01/2026 | 05/01/2026 | CERT-2026-001 | 0.05 | 0.02 | 0.1 | SIM | APROVADO |
| INS-002 | 10/01/2026 | 12/01/2026 | CERT-2026-002 | -0.03 | 0.01 | 0.08 | NÃO | APROVADO |

**O que acontece na importação:**

1. ✅ Cria/atualiza o HistoricoCalibracao com os dados
2. ✅ Busca todas as FaixaMedicao de INS-001 (ex: 4 faixas)
3. ✅ Para cada faixa, cria ResultadoFaixaCalibracao com:
   - `erro = 0.05` (do Excel)
   - `incerteza = 0.02` (do Excel)
   - `tolerancia = 0.1` (do Excel)
   - `resultado` é calculado automaticamente no save()
4. ✅ Repetiço para INS-002 com suas 3 faixas existentes

## 🔍 Validação Pós-Import

Para validar que as faixas foram associadas corretamente:

1. Acesse: `/metrologia/instrumento/{id}/`
2. Clique no histórico importado
3. Verifique a tabela "Resultados por Faixa de Medição"
4. Deve mostrar TODAS as faixas do instrumento com dados de validação

## ⚠️ Importante

- Se o instrumento não tem faixas cadastradas, nenhuma validação será criada
- Garanta que as faixas foram importadas ANTES dos históricos
- Use o fluxo: Instrumentos → Faixas → Históricos

## 📞 Suporte

Se encontrar problemas, verifique:

1. Logs do Railway: `railway logs -f`
2. Verifique se as faixas existem: Admin → Faixa de Medição
3. Verifique se o instrumento está correto: Admin → Instrumento

---

**Status:** ✅ Live em Produção  
**Última Atualização:** 16/01/2026  
**Desenvolvido por:** AI Assistant
