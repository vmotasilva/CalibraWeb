from django.db import migrations


def normalize_tipo_resposta(apps, schema_editor):
    PerguntaAuditoria = apps.get_model("auditoria", "PerguntaAuditoria")
    PerguntaAuditoria.objects.filter(tipo_resposta="BOOLEANO").update(tipo_resposta="SIM_NAO")


def reverse_normalize_tipo_resposta(apps, schema_editor):
    PerguntaAuditoria = apps.get_model("auditoria", "PerguntaAuditoria")
    PerguntaAuditoria.objects.filter(tipo_resposta="SIM_NAO").update(tipo_resposta="BOOLEANO")


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0005_alter_perguntaauditoria_tipo_resposta"),
    ]

    operations = [
        migrations.RunPython(normalize_tipo_resposta, reverse_normalize_tipo_resposta),
    ]
