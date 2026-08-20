import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0055_add_grau_nc_to_resposta_and_solicitacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="agenda",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="solicitacoes_registradas",
                to="auditoria.agendaauditoriaiso",
                verbose_name="Bloco da Agenda de Origem",
            ),
        ),
    ]
