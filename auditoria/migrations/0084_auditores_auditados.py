from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0083_ocorrencia_responsaveis_colaborador"),
        ("rh", "0035_colaborador_permissao_foto"),
    ]

    operations = [
        migrations.AddField(
            model_name="modeloauditoria",
            name="auditados",
            field=models.ManyToManyField(
                blank=True,
                help_text="Líderes auditados com acesso recorrente (somente leitura) aos relatórios deste modelo.",
                related_name="modelos_auditoria_auditados",
                to="rh.colaborador",
                verbose_name="Auditados",
            ),
        ),
        migrations.AddField(
            model_name="registroauditoria",
            name="auditores",
            field=models.ManyToManyField(
                blank=True,
                related_name="ciclos_auditoria_auditor",
                to="rh.colaborador",
                verbose_name="Auditor(es) do ciclo",
            ),
        ),
    ]
