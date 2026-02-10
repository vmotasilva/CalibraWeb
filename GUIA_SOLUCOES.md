# Guia de Soluções para Ações Corretivas/Preventivas

## Visão Geral

O módulo de **Soluções** permite gerenciar diferentes tipos de abordagens metodológicas para resolver problemas identificados através de Ações Corretivas/Preventivas. Cada tipo de solução possui sua própria estrutura, fluxo de trabalho e campos específicos.

---

## 1. Plano de Ação Simples

### Descrição
Abordagem direta e simplificada para definir e acompanhar ações corretivas/preventivas.

### Quando Usar
- Problemas simples com causas óbvias
- Ações imediatas e de curto prazo
- Quando não há necessidade de análise profunda

### Fluxo
1. **Planejamento** → Define ação proposta e responsável
2. **Em Execução** → Acompanhamento da execução
3. **Concluído** → Registra resultado
4. **Cancelado** → Se aplicável

### Campos Principais
- Ação Proposta
- Responsável pela Ação
- Data de Início e Conclusão
- Resultado

### Exemplo
```
Problema: Falta de identificação em prateleiras
Ação Proposta: Implementar etiquetas padrão em todas as prateleiras
Responsável: João Silva
Prazo: 15 dias
```

---

## 2. Relatório A3 (Toyota Production System)

### Descrição
Análise estruturada em uma página que combina problema, análise de causas e contramedidas. Metodologia originária do Toyota Production System.

### Quando Usar
- Problemas que requerem análise visual
- Quando há necessidade de documentar em formato compacto
- Melhorias operacionais e de processo

### Fluxo
1. **Planejamento** → Descrever problema e impacto
2. **Análise** → Analisar situação atual e causas
3. **Implementação** → Implementar contramedidas
4. **Validação** → Verificar efetividade

### Campos Principais
- Descrição do Problema
- Impacto do Problema
- Situação Atual
- Análise de Causas
- Causa Raiz Identificada
- Contramedidas Propostas
- Resultados Esperados
- Plano de Verificação
- Resultado da Verificação

### Exemplo
```
Problema: Taxa alta de defeitos em acabamento
Impacto: 15% de rejeição na inspeção final
Situação Atual: Processo manual sem padrão
Causa Raiz: Falta de treinamento específico
Contramedida: Implementar treinamento e checklist
Resultado Esperado: Redução para <5% de defeitos
```

---

## 3. 8 Disciplinas (8D - Ford Production System)

### Descrição
Metodologia estruturada em 8 disciplinas para resolver problemas complexos. Padrão da indústria automotiva (Ford, GM, Chrysler).

### Quando Usar
- Problemas críticos e complexos
- Quando precisa envolver múltiplas áreas
- Requer documentação robusta e rastreabilidade
- Exigência de clientes/auditorias

### Fluxo dos 8 D's
1. **D1 - Nomear o Time**: Formar equipe multidisciplinar
2. **D2 - Descrever o Problema**: Definir o que, quando, onde, quanto
3. **D3 - Conter o Problema**: Ação imediata para conter dano
4. **D4 - Análise de Causa Raiz**: Investigar causas fundamentais
5. **D5 - Contramedidas**: Desenvolver soluções permanentes
6. **D6 - Implementação**: Executar as contramedidas
7. **D7 - Verificação**: Verificar efetividade
8. **D8 - Padronização**: Prevenir recorrência e fechar caso

### Campos Principais
- D1: Time Responsável
- D2: Descrição e Especificações Afetadas
- D3: Plano de Contenção
- D4: Análise de Causas e Causa Raiz
- D5: Contramedidas Propostas
- D6: Plano de Implementação
- D7: Plano de Verificação e Resultado
- D8: Padronização e Encerramento

### Exemplo
```
D1: Time = Engenharia + Produção + Qualidade
D2: Produto X apresenta falha elétrica em 3% dos casos
D3: Revisar e rejeitar lotes afetados
D4: Soldagem deficiente em conexão Y
D5: Substituir fornecedor de componentes
D6: Nova especificação implementada em produção
D7: 0% de falhas em 1000 amostras de validação
D8: Novo procedimento de inspeção documentado
```

---

## 4. RNC - Relatório de Não Conformidade (ISO 9001)

### Descrição
Formato padrão para documentar não conformidades encontradas durante processos de garantia de qualidade. Segue requisitos ISO 9001.

### Quando Usar
- Auditoria interna/externa identifica não conformidade
- Clientes relatam reclamação
- Processo de certificação ISO 9001
- Rastreabilidade normativa obrigatória

### Fluxo
1. **Proposta** → RNC aberta
2. **Análise** → Investigação de causas
3. **Aprovada** → Para execução
4. **Implementada** → Validação
5. **Rejeitada** → Se não procedente

### Campos Principais
- Descrição da Não Conformidade
- Tipo de NC (Maior/Menor)
- Análise de Causas
- Causa Raiz
- Ação Imediata
- Ação Corretiva
- Ação Preventiva
- Plano de Verificação
- Resultado

### Exemplo
```
NC: Documentação de rastreabilidade incompleta
Tipo: Maior
Causa Raiz: Sistema de registro manual com gaps
Ação Imediata: Revisar todos os registros do lote
Ação Corretiva: Implementar sistema eletrônico de rastreabilidade
Ação Preventiva: Treinamento para novos operadores
```

---

## 5. Gestão de Mudança

### Descrição
Processo estruturado para avaliar, aprovar e implementar mudanças em processos, sistemas ou pessoas. Garante rastreabilidade e validação de impactos.

### Quando Usar
- Mudanças em procedimentos operacionais
- Implementação de novos sistemas ou ferramentas
- Mudanças no layout ou equipamentos
- Mudanças organizacionais que afetam processos

### Fluxo
1. **Proposta** → Descrição da mudança
2. **Análise** → Avaliação de impactos
3. **Aprovada** → Liberada para implementação
4. **Implementada** → Executada
5. **Rejeitada** → Não procedente

### Campos Principais
- Descrição da Mudança
- Motivação/Justificativa
- Impacto em Processos
- Impacto em Sistemas
- Impacto em Pessoas
- Plano de Implementação
- Data de Implementação
- Status de Aprovação
- Plano de Validação
- Resultado da Validação

### Exemplo
```
Mudança: Alterar sequência de montagem na linha A
Justificativa: Reduzir tempo de ciclo em 10%
Impacto em Processos: Resequenciar estações 1-5
Impacto em Pessoas: Treinamento de 15 operadores
Plano de Validação: 2 semanas de produção piloto
```

---

## 6. Revisão Gerencial

### Descrição
Análise estratégica e de conformidade conduzida pela gerência para identificar oportunidades de melhoria e recomendações estruturais.

### Quando Usar
- Revisão de resultados de auditoria
- Análise periódica de desempenho
- Recomendações estratégicas
- Identificação de oportunidades de melhoria

### Fluxo
1. **Proposta** → Escopo da revisão
2. **Análise** → Condução da revisão
3. **Relatório** → Achados e recomendações
4. **Plano de Ação** → Definir implementação
5. **Acompanhamento** → Monitorar resultados

### Campos Principais
- Descrição da Revisão
- Escopo da Revisão
- Achados Principais
- Oportunidades de Melhoria
- Recomendações
- Prioridade de Implementação (Alta/Média/Baixa)
- Responsável pela Implementação
- Data Alvo de Implementação
- Resultado
- Data de Conclusão

### Exemplo
```
Revisão: Análise de Eficácia do Sistema de Qualidade
Escopo: Processos de Produção (Jan-Jun 2025)
Achado 1: 5 auditorias abertas sem plano de ação
Achado 2: Taxa de treinamento 30% abaixo da meta
Recomendação: Implementar matriz de rastreamento
Prioridade: Alta
Implementação até: 30/03/2025
```

---

## Quadro Comparativo

| Aspecto | Plano de Ação | A3 | 8D | RNC | Gestão de Mudança | Revisão Gerencial |
|---------|--------------|----|----|-----|-------------------|-------------------|
| **Complexidade** | Baixa | Média | Alta | Média | Média-Alta | Alta |
| **Tempo Típico** | 1-2 semanas | 2-4 semanas | 6-12 semanas | 2-6 semanas | 1-3 meses | 2-4 semanas |
| **Equipes Envolvidas** | 1-2 | 2-3 | 3-5+ | 2-3 | 2-4 | 3-5+ |
| **Documentação** | Básica | Compacta (1 página) | Completa | Estruturada | Detalhada | Executiva |
| **Rastreabilidade** | Média | Média | Alta | Alta | Alta | Alta |
| **Quando Usar** | Simples | Processos | Crítico | Conformidade | Mudanças | Estratégia |

---

## Dicas de Boas Práticas

### Geral
- ✅ Nomear responsável claro em cada solução
- ✅ Definir prazos realistas
- ✅ Envolver stakeholders relevantes
- ✅ Documentar decisões e justificativas
- ✅ Revisar regularmente o progresso

### Para Cada Tipo
- **Plano de Ação**: Manter simplificado, evitar excesso de burocracia
- **A3**: Respeitar limite de 1 página, ser conciso
- **8D**: Garantir que cada D seja completo antes de avançar
- **RNC**: Documentar conforme requisitos ISO 9001
- **Gestão de Mudança**: Sempre incluir plano de validação
- **Revisão Gerencial**: Focar em recomendações acionáveis

### Integração com Ações Corretivas
- Toda Ação Corretiva deve ter pelo menos uma Solução
- Múltiplas soluções podem ser criadas para a mesma ação
- Status da solução deve estar alinhado com status da ação
- Validar antes de encerrar a ação corretiva

---

## Fluxograma Geral

```
┌─────────────────────┐
│  Ação Corretiva     │
│  Identificada       │
└──────────┬──────────┘
           │
           ├─→ Problema Simples? → Plano de Ação
           │
           ├─→ Processo? → A3
           │
           ├─→ Crítico/Complexo? → 8D
           │
           ├─→ Não Conformidade? → RNC
           │
           ├─→ Mudança Necessária? → Gestão de Mudança
           │
           └─→ Análise Estratégica? → Revisão Gerencial
```

---

**Última Atualização**: 10 de fevereiro de 2025
**Versão**: 1.0
