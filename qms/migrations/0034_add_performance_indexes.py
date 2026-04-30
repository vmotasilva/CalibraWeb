# Generated migration for performance indexes - Fase 6 Task #1

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qms', '0032_phase9_checkpoint'),
    ]

    operations = [
        # Índice para queries frequentes em Instrumento
        migrations.AddIndex(
            model_name='instrumento',
            index=models.Index(
                fields=['ativo', 'tag'],
                name='instr_ativo_tag_idx',
            ),
        ),
        
        # Índice para filtros por categoria
        migrations.AddIndex(
            model_name='instrumento',
            index=models.Index(
                fields=['categoria', 'ativo'],
                name='instr_categoria_ativo_idx',
            ),
        ),
        
        # Índice para ordenação por data de calibração
        migrations.AddIndex(
            model_name='instrumento',
            index=models.Index(
                fields=['data_proxima_calibracao', 'ativo'],
                name='instr_proxima_calib_idx',
            ),
        ),
        
        # Índice para filtros por setor
        migrations.AddIndex(
            model_name='instrumento',
            index=models.Index(
                fields=['setor', 'ativo'],
                name='instr_setor_ativo_idx',
            ),
        ),
        
        # Índice para busca por tag (muito usado)
        migrations.AddIndex(
            model_name='instrumento',
            index=models.Index(
                fields=['tag'],
                name='instr_tag_idx',
            ),
        ),

        # Índices para HistoricoCalibracao
        migrations.AddIndex(
            model_name='historicocalibracao',
            index=models.Index(
                fields=['instrumento', 'data_calibracao'],
                name='hist_instr_data_idx',
            ),
        ),
        
        # Índice para resultado de aprovação
        migrations.AddIndex(
            model_name='historicocalibracao',
            index=models.Index(
                fields=['resultado', 'data_calibracao'],
                name='hist_resultado_data_idx',
            ),
        ),
        
        # Índice para data de calibração (queries de vencidos)
        migrations.AddIndex(
            model_name='historicocalibracao',
            index=models.Index(
                fields=['data_calibracao'],
                name='hist_data_calib_idx',
            ),
        ),
        
        # Índice para próxima calibração
        migrations.AddIndex(
            model_name='historicocalibracao',
            index=models.Index(
                fields=['proxima_calibracao'],
                name='hist_proxima_calib_idx',
            ),
        ),

        # Índices para Setor
        migrations.AddIndex(
            model_name='setor',
            index=models.Index(
                fields=['nome'],
                name='setor_nome_idx',
            ),
        ),

        # Índices para CategoriaInstrumento
        migrations.AddIndex(
            model_name='categoriainstrumento',
            index=models.Index(
                fields=['nome'],
                name='categoria_nome_idx',
            ),
        ),
    ]
