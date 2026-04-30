-- Índices para otimizar o dashboard de treinamentos
-- OBS: Se você aplicar as migrations do Django (recomendado), este script não é necessário.
-- Este arquivo existe apenas para execução manual/emergencial.

-- Índices para a tabela de registros de treinamento (procedures.RegistroTreinamento)
CREATE INDEX IF NOT EXISTS regtrein_colaborador_id_idx ON procedures_registrotreinamento (colaborador_id);
CREATE INDEX IF NOT EXISTS regtrein_procedimento_id_idx ON procedures_registrotreinamento (procedimento_id);
CREATE INDEX IF NOT EXISTS regtrein_ativo_data_idx ON procedures_registrotreinamento (ativo, data_treinamento);
CREATE INDEX IF NOT EXISTS regtrein_ativo_col_proc_idx ON procedures_registrotreinamento (ativo, colaborador_id, procedimento_id);

-- Índices para a tabela de colaboradores
CREATE INDEX IF NOT EXISTS rh_colaborador_turno_idx ON rh_colaborador (turno);
CREATE INDEX IF NOT EXISTS rh_colab_dash_filters_idx ON rh_colaborador (is_active, afastado, em_ferias, turno, setor_id);

-- Índices para a tabela de procedimentos
CREATE INDEX IF NOT EXISTS proc_criticidade_idx ON procedures_procedimento (criticidade);
CREATE INDEX IF NOT EXISTS proc_matriz_idx ON procedures_procedimento (matriz);
CREATE INDEX IF NOT EXISTS proc_sub_area_idx ON procedures_procedimento (sub_area);
