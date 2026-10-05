# -*- coding: utf-8 -*-
"""
Catálogo de Modelos (Templates) de Diagramas e Estruturas Visuais
Inspirado em ferramentas profissionais de mapeamento mental e fluxogramas (XMind, Miro, EdrawMind).
"""

TEMPLATES_DIAGRAMAS = [
    {
        "id": "fluxograma_padrao",
        "nome": "Fluxograma de Processo (DOC.071)",
        "categoria": "Processos & QMS",
        "categoria_slug": "processos",
        "icone": "bi bi-diagram-3-fill",
        "descricao": "Fluxo operacional padrão com raias, etapas sequenciais e ponto de decisão (Sim/Não).",
        "destaque": True,
        "svg_tipo": "flowchart",
        "gerar_topologia": lambda dep="Metrologia": {
            "nodes": [
                {"id": "1", "type": "start", "position": {"x": 80, "y": 80}, "data": {"label": "Início do Processo", "stepId": "1", "lane": dep}},
                {"id": "2", "type": "process", "position": {"x": 320, "y": 80}, "data": {"label": "Entrada / Recebimento", "stepId": "2", "lane": dep}},
                {"id": "3", "type": "process", "position": {"x": 560, "y": 80}, "data": {"label": "Execução da Atividade", "stepId": "3", "lane": dep}},
                {"id": "4", "type": "decision", "position": {"x": 800, "y": 60}, "data": {"label": "Conforme?", "stepId": "4", "lane": dep}},
                {"id": "5", "type": "process", "position": {"x": 800, "y": 240}, "data": {"label": "Tratativa de Não Conformidade", "stepId": "5", "lane": dep}},
                {"id": "6", "type": "end", "position": {"x": 1060, "y": 80}, "data": {"label": "Fim / Liberação", "stepId": "6", "lane": dep}},
            ],
            "edges": [
                {"id": "e-1-2", "source": "1", "target": "2", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-2-3", "source": "2", "target": "3", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-3-4", "source": "3", "target": "4", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-4-6", "source": "4", "target": "6", "sourceHandle": "right", "targetHandle": "left", "label": "Sim"},
                {"id": "e-4-5", "source": "4", "target": "5", "sourceHandle": "bottom", "targetHandle": "top", "label": "Não"},
                {"id": "e-5-3", "source": "5", "target": "3", "sourceHandle": "left", "targetHandle": "bottom", "label": "Reexecutar"},
            ],
            "grid_data": [
                {"stepId": "1", "lane": dep, "type": "start", "label": "Início do Processo", "next": [{"targetId": "2"}]},
                {"stepId": "2", "lane": dep, "type": "process", "label": "Entrada / Recebimento", "next": [{"targetId": "3"}]},
                {"stepId": "3", "lane": dep, "type": "process", "label": "Execução da Atividade", "next": [{"targetId": "4"}]},
                {"stepId": "4", "lane": dep, "type": "decision", "label": "Conforme?", "next": [{"targetId": "6", "condition": "Sim"}, {"targetId": "5", "condition": "Não"}]},
                {"stepId": "5", "lane": dep, "type": "process", "label": "Tratativa de Não Conformidade", "next": [{"targetId": "3", "condition": "Reexecutar"}]},
                {"stepId": "6", "lane": dep, "type": "end", "label": "Fim / Liberação", "next": []}
            ]
        }
    },
    {
        "id": "organograma",
        "nome": "Organograma Hierárquico (Org Chart)",
        "categoria": "Estruturas & Gestão",
        "categoria_slug": "estruturas",
        "icone": "bi bi-diagram-2-fill",
        "descricao": "Estrutura organizacional em árvore de cima para baixo com cargos, setores e lideranças.",
        "destaque": True,
        "svg_tipo": "orgchart",
        "gerar_topologia": lambda dep="Geral": {
            "nodes": [
                {"id": "org-root", "type": "process", "position": {"x": 500, "y": 40}, "data": {"label": "Direção / Gerência Geral", "stepId": "1", "lane": "Liderança"}},
                {"id": "org-m1", "type": "process", "position": {"x": 200, "y": 180}, "data": {"label": "Coordenação da Qualidade", "stepId": "2", "lane": "Gestão Tática"}},
                {"id": "org-m2", "type": "process", "position": {"x": 500, "y": 180}, "data": {"label": "Supervisão do Laboratório", "stepId": "3", "lane": "Gestão Tática"}},
                {"id": "org-m3", "type": "process", "position": {"x": 800, "y": 180}, "data": {"label": "Engenharia & Métodos", "stepId": "4", "lane": "Gestão Tática"}},
                {"id": "org-s1", "type": "process", "position": {"x": 100, "y": 320}, "data": {"label": "Analista da Qualidade", "stepId": "5", "lane": "Operacional"}},
                {"id": "org-s2", "type": "process", "position": {"x": 300, "y": 320}, "data": {"label": "Auditor Interno", "stepId": "6", "lane": "Operacional"}},
                {"id": "org-s3", "type": "process", "position": {"x": 500, "y": 320}, "data": {"label": "Técnico Metrologista", "stepId": "7", "lane": "Operacional"}},
                {"id": "org-s4", "type": "process", "position": {"x": 700, "y": 320}, "data": {"label": "Auxiliar de Laboratório", "stepId": "8", "lane": "Operacional"}},
                {"id": "org-s5", "type": "process", "position": {"x": 900, "y": 320}, "data": {"label": "Especialista em Validação", "stepId": "9", "lane": "Operacional"}},
            ],
            "edges": [
                {"id": "e-root-m1", "source": "org-root", "target": "org-m1", "sourceHandle": "bottom", "targetHandle": "top"},
                {"id": "e-root-m2", "source": "org-root", "target": "org-m2", "sourceHandle": "bottom", "targetHandle": "top"},
                {"id": "e-root-m3", "source": "org-root", "target": "org-m3", "sourceHandle": "bottom", "targetHandle": "top"},
                {"id": "e-m1-s1", "source": "org-m1", "target": "org-s1", "sourceHandle": "bottom", "targetHandle": "top"},
                {"id": "e-m1-s2", "source": "org-m1", "target": "org-s2", "sourceHandle": "bottom", "targetHandle": "top"},
                {"id": "e-m2-s3", "source": "org-m2", "target": "org-s3", "sourceHandle": "bottom", "targetHandle": "top"},
                {"id": "e-m2-s4", "source": "org-m2", "target": "org-s4", "sourceHandle": "bottom", "targetHandle": "top"},
                {"id": "e-m3-s5", "source": "org-m3", "target": "org-s5", "sourceHandle": "bottom", "targetHandle": "top"},
            ],
            "grid_data": [
                {"stepId": "1", "lane": "Liderança", "type": "process", "label": "Direção / Gerência Geral", "next": [{"targetId": "2"}, {"targetId": "3"}, {"targetId": "4"}]},
                {"stepId": "2", "lane": "Gestão Tática", "type": "process", "label": "Coordenação da Qualidade", "next": [{"targetId": "5"}, {"targetId": "6"}]},
                {"stepId": "3", "lane": "Gestão Tática", "type": "process", "label": "Supervisão do Laboratório", "next": [{"targetId": "7"}, {"targetId": "8"}]},
                {"stepId": "4", "lane": "Gestão Tática", "type": "process", "label": "Engenharia & Métodos", "next": [{"targetId": "9"}]},
                {"stepId": "5", "lane": "Operacional", "type": "process", "label": "Analista da Qualidade", "next": []},
                {"stepId": "6", "lane": "Operacional", "type": "process", "label": "Auditor Interno", "next": []},
                {"stepId": "7", "lane": "Operacional", "type": "process", "label": "Técnico Metrologista", "next": []},
                {"stepId": "8", "lane": "Operacional", "type": "process", "label": "Auxiliar de Laboratório", "next": []},
                {"stepId": "9", "lane": "Operacional", "type": "process", "label": "Especialista em Validação", "next": []},
            ]
        }
    },
    {
        "id": "mapa_mental",
        "nome": "Mapa Mental Radial (Mind Map)",
        "categoria": "Planejamento & Ideias",
        "categoria_slug": "mapas_mentais",
        "icone": "bi bi-node-plus-fill",
        "descricao": "Tópico central com ramificações balanceadas para a esquerda e para a direita.",
        "destaque": True,
        "svg_tipo": "mindmap",
        "gerar_topologia": lambda dep="Planejamento": {
            "nodes": [
                {"id": "center", "type": "start", "position": {"x": 540, "y": 200}, "data": {"label": "Tópico Central / Objetivo", "stepId": "c", "lane": "Núcleo"}},
                # Lado Direito
                {"id": "r1", "type": "process", "position": {"x": 820, "y": 100}, "data": {"label": "1. Planejamento", "stepId": "r1", "lane": "Direita"}},
                {"id": "r1-1", "type": "process", "position": {"x": 1060, "y": 70}, "data": {"label": "Cronograma & Prazos", "stepId": "r11", "lane": "Direita"}},
                {"id": "r1-2", "type": "process", "position": {"x": 1060, "y": 130}, "data": {"label": "Recursos & Orçamento", "stepId": "r12", "lane": "Direita"}},
                {"id": "r2", "type": "process", "position": {"x": 820, "y": 280}, "data": {"label": "2. Execução", "stepId": "r2", "lane": "Direita"}},
                {"id": "r2-1", "type": "process", "position": {"x": 1060, "y": 280}, "data": {"label": "Procedimentos & Testes", "stepId": "r21", "lane": "Direita"}},
                # Lado Esquerdo
                {"id": "l1", "type": "process", "position": {"x": 260, "y": 100}, "data": {"label": "3. Monitoramento", "stepId": "l1", "lane": "Esquerda"}},
                {"id": "l1-1", "type": "process", "position": {"x": 20, "y": 70}, "data": {"label": "KPIs & Indicadores", "stepId": "l11", "lane": "Esquerda"}},
                {"id": "l1-2", "type": "process", "position": {"x": 20, "y": 130}, "data": {"label": "Auditorias & Controles", "stepId": "l12", "lane": "Esquerda"}},
                {"id": "l2", "type": "process", "position": {"x": 260, "y": 280}, "data": {"label": "4. Melhoria Contínua", "stepId": "l2", "lane": "Esquerda"}},
                {"id": "l2-1", "type": "process", "position": {"x": 20, "y": 280}, "data": {"label": "Planos de Ação (CAPA)", "stepId": "l21", "lane": "Esquerda"}},
            ],
            "edges": [
                {"id": "e-c-r1", "source": "center", "target": "r1", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-r1-r11", "source": "r1", "target": "r1-1", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-r1-r12", "source": "r1", "target": "r1-2", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-c-r2", "source": "center", "target": "r2", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-r2-r21", "source": "r2", "target": "r2-1", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-c-l1", "source": "center", "target": "l1", "sourceHandle": "left", "targetHandle": "right"},
                {"id": "e-l1-l11", "source": "l1", "target": "l1-1", "sourceHandle": "left", "targetHandle": "right"},
                {"id": "e-l1-l12", "source": "l1", "target": "l1-2", "sourceHandle": "left", "targetHandle": "right"},
                {"id": "e-c-l2", "source": "center", "target": "l2", "sourceHandle": "left", "targetHandle": "right"},
                {"id": "e-l2-l21", "source": "l2", "target": "l2-1", "sourceHandle": "left", "targetHandle": "right"},
            ],
            "grid_data": [
                {"stepId": "c", "lane": "Núcleo", "type": "start", "label": "Tópico Central / Objetivo", "next": [{"targetId": "r1"}, {"targetId": "r2"}, {"targetId": "l1"}, {"targetId": "l2"}]},
                {"stepId": "r1", "lane": "Direita", "type": "process", "label": "1. Planejamento", "next": [{"targetId": "r11"}, {"targetId": "r12"}]},
                {"stepId": "r11", "lane": "Direita", "type": "process", "label": "Cronograma & Prazos", "next": []},
                {"stepId": "r12", "lane": "Direita", "type": "process", "label": "Recursos & Orçamento", "next": []},
                {"stepId": "r2", "lane": "Direita", "type": "process", "label": "2. Execução", "next": [{"targetId": "r21"}]},
                {"stepId": "r21", "lane": "Direita", "type": "process", "label": "Procedimentos & Testes", "next": []},
                {"stepId": "l1", "lane": "Esquerda", "type": "process", "label": "3. Monitoramento", "next": [{"targetId": "l11"}, {"targetId": "l12"}]},
                {"stepId": "l11", "lane": "Esquerda", "type": "process", "label": "KPIs & Indicadores", "next": []},
                {"stepId": "l12", "lane": "Esquerda", "type": "process", "label": "Auditorias & Controles", "next": []},
                {"stepId": "l2", "lane": "Esquerda", "type": "process", "label": "4. Melhoria Contínua", "next": [{"targetId": "l21"}]},
                {"stepId": "l21", "lane": "Esquerda", "type": "process", "label": "Planos de Ação (CAPA)", "next": []},
            ]
        }
    },
    {
        "id": "ishikawa",
        "nome": "Diagrama de Ishikawa (Espinha de Peixe / 6M)",
        "categoria": "Qualidade & Análise de Falhas",
        "categoria_slug": "qualidade",
        "icone": "bi bi-activity",
        "descricao": "Análise de causa e efeito estruturada nos 6M: Método, Máquina, Material, Mão de Obra, Meio Ambiente e Medição.",
        "destaque": True,
        "svg_tipo": "fishbone",
        "gerar_topologia": lambda dep="Qualidade": {
            "nodes": [
                # Cabeça do Peixe (Efeito)
                {"id": "effect", "type": "decision", "position": {"x": 1000, "y": 200}, "data": {"label": "Problema / Efeito Central", "stepId": "eff", "lane": "Efeito"}},
                # Espinhas Superiores
                {"id": "m_metodo", "type": "process", "position": {"x": 300, "y": 60}, "data": {"label": "Método", "stepId": "m1", "lane": "Causas Superiores"}},
                {"id": "c_metodo1", "type": "process", "position": {"x": 140, "y": 60}, "data": {"label": "Procedimento Desatualizado", "stepId": "c1", "lane": "Causas Superiores"}},
                {"id": "m_maquina", "type": "process", "position": {"x": 580, "y": 60}, "data": {"label": "Máquina / Equipamento", "stepId": "m2", "lane": "Causas Superiores"}},
                {"id": "c_maquina1", "type": "process", "position": {"x": 740, "y": 60}, "data": {"label": "Calibração Vencida", "stepId": "c2", "lane": "Causas Superiores"}},
                {"id": "m_material", "type": "process", "position": {"x": 850, "y": 60}, "data": {"label": "Material / Insumo", "stepId": "m3", "lane": "Causas Superiores"}},
                # Espinhas Inferiores
                {"id": "m_maodeobra", "type": "process", "position": {"x": 300, "y": 340}, "data": {"label": "Mão de Obra", "stepId": "m4", "lane": "Causas Inferiores"}},
                {"id": "c_mao1", "type": "process", "position": {"x": 140, "y": 340}, "data": {"label": "Falta de Treinamento", "stepId": "c4", "lane": "Causas Inferiores"}},
                {"id": "m_meio", "type": "process", "position": {"x": 580, "y": 340}, "data": {"label": "Meio Ambiente", "stepId": "m5", "lane": "Causas Inferiores"}},
                {"id": "c_meio1", "type": "process", "position": {"x": 740, "y": 340}, "data": {"label": "Variação de Temperatura", "stepId": "c5", "lane": "Causas Inferiores"}},
                {"id": "m_medicao", "type": "process", "position": {"x": 850, "y": 340}, "data": {"label": "Medição", "stepId": "m6", "lane": "Causas Inferiores"}},
            ],
            "edges": [
                {"id": "e-m1-eff", "source": "m_metodo", "target": "effect", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-c1-m1", "source": "c_metodo1", "target": "m_metodo", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-m2-eff", "source": "m_maquina", "target": "effect", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-c2-m2", "source": "c_maquina1", "target": "m_maquina", "sourceHandle": "left", "targetHandle": "right"},
                {"id": "e-m3-eff", "source": "m_material", "target": "effect", "sourceHandle": "bottom", "targetHandle": "left"},
                {"id": "e-m4-eff", "source": "m_maodeobra", "target": "effect", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-c4-m4", "source": "c_mao1", "target": "m_maodeobra", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-m5-eff", "source": "m_meio", "target": "effect", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-c5-m5", "source": "c_meio1", "target": "m_meio", "sourceHandle": "left", "targetHandle": "right"},
                {"id": "e-m6-eff", "source": "m_medicao", "target": "effect", "sourceHandle": "top", "targetHandle": "left"},
            ],
            "grid_data": [
                {"stepId": "eff", "lane": "Efeito", "type": "decision", "label": "Problema / Efeito Central", "next": []},
                {"stepId": "m1", "lane": "Causas Superiores", "type": "process", "label": "Método", "next": [{"targetId": "eff"}]},
                {"stepId": "c1", "lane": "Causas Superiores", "type": "process", "label": "Procedimento Desatualizado", "next": [{"targetId": "m1"}]},
                {"stepId": "m2", "lane": "Causas Superiores", "type": "process", "label": "Máquina / Equipamento", "next": [{"targetId": "eff"}]},
                {"stepId": "c2", "lane": "Causas Superiores", "type": "process", "label": "Calibração Vencida", "next": [{"targetId": "m2"}]},
                {"stepId": "m3", "lane": "Causas Superiores", "type": "process", "label": "Material / Insumo", "next": [{"targetId": "eff"}]},
                {"stepId": "m4", "lane": "Causas Inferiores", "type": "process", "label": "Mão de Obra", "next": [{"targetId": "eff"}]},
                {"stepId": "c4", "lane": "Causas Inferiores", "type": "process", "label": "Falta de Treinamento", "next": [{"targetId": "m4"}]},
                {"stepId": "m5", "lane": "Causas Inferiores", "type": "process", "label": "Meio Ambiente", "next": [{"targetId": "eff"}]},
                {"stepId": "c5", "lane": "Causas Inferiores", "type": "process", "label": "Variação de Temperatura", "next": [{"targetId": "m5"}]},
                {"stepId": "m6", "lane": "Causas Inferiores", "type": "process", "label": "Medição", "next": [{"targetId": "eff"}]},
            ]
        }
    },
    {
        "id": "timeline",
        "nome": "Linha do Tempo / Cronograma (Timeline)",
        "categoria": "Projetos & Prazos",
        "categoria_slug": "projetos",
        "icone": "bi bi-calendar-range-fill",
        "descricao": "Eixo horizontal progressivo com marcos, fases de entrega e validações temporais.",
        "destaque": False,
        "svg_tipo": "timeline",
        "gerar_topologia": lambda dep="Projetos": {
            "nodes": [
                {"id": "t1", "type": "start", "position": {"x": 60, "y": 140}, "data": {"label": "Fase 1: Diagnóstico", "stepId": "t1", "lane": "Marcos"}},
                {"id": "t1-s", "type": "process", "position": {"x": 60, "y": 260}, "data": {"label": "Levantamento de Requisitos", "stepId": "t1s", "lane": "Entregáveis"}},
                {"id": "t2", "type": "process", "position": {"x": 360, "y": 140}, "data": {"label": "Fase 2: Desenvolvimento", "stepId": "t2", "lane": "Marcos"}},
                {"id": "t2-s", "type": "process", "position": {"x": 360, "y": 260}, "data": {"label": "Construção de Métodos e POPs", "stepId": "t2s", "lane": "Entregáveis"}},
                {"id": "t3", "type": "decision", "position": {"x": 660, "y": 120}, "data": {"label": "Fase 3: Qualificação", "stepId": "t3", "lane": "Marcos"}},
                {"id": "t3-s", "type": "process", "position": {"x": 660, "y": 260}, "data": {"label": "Auditoria Piloto / Testes", "stepId": "t3s", "lane": "Entregáveis"}},
                {"id": "t4", "type": "end", "position": {"x": 960, "y": 140}, "data": {"label": "Fase 4: Go-Live / Homologação", "stepId": "t4", "lane": "Marcos"}},
            ],
            "edges": [
                {"id": "e-t1-t2", "source": "t1", "target": "t2", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-t1-t1s", "source": "t1", "target": "t1-s", "sourceHandle": "bottom", "targetHandle": "top"},
                {"id": "e-t2-t3", "source": "t2", "target": "t3", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-t2-t2s", "source": "t2", "target": "t2-s", "sourceHandle": "bottom", "targetHandle": "top"},
                {"id": "e-t3-t4", "source": "t3", "target": "t4", "sourceHandle": "right", "targetHandle": "left", "label": "Aprovado"},
                {"id": "e-t3-t3s", "source": "t3", "target": "t3-s", "sourceHandle": "bottom", "targetHandle": "top"},
            ],
            "grid_data": [
                {"stepId": "t1", "lane": "Marcos", "type": "start", "label": "Fase 1: Diagnóstico", "next": [{"targetId": "t2"}, {"targetId": "t1s"}]},
                {"stepId": "t1s", "lane": "Entregáveis", "type": "process", "label": "Levantamento de Requisitos", "next": []},
                {"stepId": "t2", "lane": "Marcos", "type": "process", "label": "Fase 2: Desenvolvimento", "next": [{"targetId": "t3"}, {"targetId": "t2s"}]},
                {"stepId": "t2s", "lane": "Entregáveis", "type": "process", "label": "Construção de Métodos e POPs", "next": []},
                {"stepId": "t3", "lane": "Marcos", "type": "decision", "label": "Fase 3: Qualificação", "next": [{"targetId": "t4", "condition": "Aprovado"}, {"targetId": "t3s"}]},
                {"stepId": "t3s", "lane": "Entregáveis", "type": "process", "label": "Auditoria Piloto / Testes", "next": []},
                {"stepId": "t4", "lane": "Marcos", "type": "end", "label": "Fase 4: Go-Live / Homologação", "next": []},
            ]
        }
    },
    {
        "id": "logic_chart",
        "nome": "Diagrama Lógico Horizontal (Logic Chart)",
        "categoria": "Estruturas & Gestão",
        "categoria_slug": "estruturas",
        "icone": "bi bi-distribute-horizontal",
        "descricao": "Tópico principal à esquerda desdobrado horizontalmente em sub-etapas e detalhamentos.",
        "destaque": False,
        "svg_tipo": "logicchart",
        "gerar_topologia": lambda dep="Metrologia": {
            "nodes": [
                {"id": "lc-root", "type": "start", "position": {"x": 50, "y": 180}, "data": {"label": "Escopo Central", "stepId": "lcr", "lane": "Entrada"}},
                {"id": "lc-m1", "type": "process", "position": {"x": 350, "y": 80}, "data": {"label": "1. Entrada de Dados", "stepId": "lcm1", "lane": "Etapas"}},
                {"id": "lc-m1-1", "type": "process", "position": {"x": 650, "y": 60}, "data": {"label": "Coleta de Leituras", "stepId": "lc11", "lane": "Sub-etapas"}},
                {"id": "lc-m1-2", "type": "process", "position": {"x": 650, "y": 110}, "data": {"label": "Checagem de Padrão", "stepId": "lc12", "lane": "Sub-etapas"}},
                {"id": "lc-m2", "type": "process", "position": {"x": 350, "y": 260}, "data": {"label": "2. Processamento e Cálculo", "stepId": "lcm2", "lane": "Etapas"}},
                {"id": "lc-m2-1", "type": "process", "position": {"x": 650, "y": 240}, "data": {"label": "Cálculo de Incerteza (GUM)", "stepId": "lc21", "lane": "Sub-etapas"}},
                {"id": "lc-m2-2", "type": "process", "position": {"x": 650, "y": 290}, "data": {"label": "Determinação de Erro Máximo", "stepId": "lc22", "lane": "Sub-etapas"}},
            ],
            "edges": [
                {"id": "e-lcr-m1", "source": "lc-root", "target": "lc-m1", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-lcr-m2", "source": "lc-root", "target": "lc-m2", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-m1-11", "source": "lc-m1", "target": "lc-m1-1", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-m1-12", "source": "lc-m1", "target": "lc-m1-2", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-m2-21", "source": "lc-m2", "target": "lc-m2-1", "sourceHandle": "right", "targetHandle": "left"},
                {"id": "e-m2-22", "source": "lc-m2", "target": "lc-m2-2", "sourceHandle": "right", "targetHandle": "left"},
            ],
            "grid_data": [
                {"stepId": "lcr", "lane": "Entrada", "type": "start", "label": "Escopo Central", "next": [{"targetId": "lcm1"}, {"targetId": "lcm2"}]},
                {"stepId": "lcm1", "lane": "Etapas", "type": "process", "label": "1. Entrada de Dados", "next": [{"targetId": "lc11"}, {"targetId": "lc12"}]},
                {"stepId": "lc11", "lane": "Sub-etapas", "type": "process", "label": "Coleta de Leituras", "next": []},
                {"stepId": "lc12", "lane": "Sub-etapas", "type": "process", "label": "Checagem de Padrão", "next": []},
                {"stepId": "lcm2", "lane": "Etapas", "type": "process", "label": "2. Processamento e Cálculo", "next": [{"targetId": "lc21"}, {"targetId": "lc22"}]},
                {"stepId": "lc21", "lane": "Sub-etapas", "type": "process", "label": "Cálculo de Incerteza (GUM)", "next": []},
                {"stepId": "lc22", "lane": "Sub-etapas", "type": "process", "label": "Determinação de Erro Máximo", "next": []},
            ]
        }
    }
]


def obter_catalogo_templates():
    """Retorna lista formatada de todos os templates disponíveis para renderização na view."""
    return TEMPLATES_DIAGRAMAS


def obter_topologia_por_template_id(template_id: str, departamento: str = "Metrologia") -> dict:
    """Retorna a estrutura de dados (nodes, edges, grid_data) para o template_id especificado."""
    for tpl in TEMPLATES_DIAGRAMAS:
        if tpl["id"] == template_id:
            return tpl["gerar_topologia"](departamento or "Metrologia")
    # Fallback para o primeiro
    return TEMPLATES_DIAGRAMAS[0]["gerar_topologia"](departamento or "Metrologia")
