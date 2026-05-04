from django.db import migrations, models
import django.db.models.deletion


def populate_tipo_maquina(apps, schema_editor):
    ModeloAuditoria = apps.get_model("insumos", "ModeloAuditoria")

    for modelo in ModeloAuditoria.objects.all():
        if modelo.tipo_maquina_id:
            continue

        categoria_ids = [
            categoria_id
            for categoria_id in modelo.maquinas.values_list("categoria_id", flat=True).distinct()
            if categoria_id
        ]
        if len(categoria_ids) == 1:
            modelo.tipo_maquina_id = categoria_ids[0]
            modelo.save(update_fields=["tipo_maquina"])


class Migration(migrations.Migration):

    dependencies = [
        ("insumos", "0006_categoriainsumo_modeloauditoria_maquinas_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="modeloauditoria",
            name="tipo_maquina",
            field=models.ForeignKey(
                blank=True,
                help_text="Tipo de maquina ao qual este insumo se aplica, quando houver.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cadastros_insumos",
                to="maquinas.categoriamaquina",
                verbose_name="Tipo de maquina",
            ),
        ),
        migrations.RunPython(populate_tipo_maquina, migrations.RunPython.noop),
    ]