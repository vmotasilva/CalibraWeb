from django.db import migrations, models


def add_exibir_grafico_column(_apps, schema_editor):
    table_name = "auditoria_perguntaauditoria"
    connection = schema_editor.connection
    quote_name = schema_editor.quote_name

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

    if "exibir_grafico" not in columns:
        if connection.vendor == "sqlite":
            schema_editor.execute(
                f"ALTER TABLE {quote_name(table_name)} ADD COLUMN {quote_name('exibir_grafico')} bool NOT NULL DEFAULT 1"
            )
            return

        if connection.vendor == "postgresql":
            schema_editor.execute(
                f"ALTER TABLE {quote_name(table_name)} ADD COLUMN {quote_name('exibir_grafico')} boolean NOT NULL DEFAULT TRUE"
            )
            return

        schema_editor.execute(
            f"ALTER TABLE {quote_name(table_name)} ADD COLUMN {quote_name('exibir_grafico')} boolean NOT NULL DEFAULT 1"
        )
        return

    if connection.vendor == "postgresql":
        schema_editor.execute(
            f"UPDATE {quote_name(table_name)} SET {quote_name('exibir_grafico')} = TRUE WHERE {quote_name('exibir_grafico')} IS NULL"
        )
        schema_editor.execute(
            f"ALTER TABLE {quote_name(table_name)} ALTER COLUMN {quote_name('exibir_grafico')} SET DEFAULT TRUE"
        )
        schema_editor.execute(
            f"ALTER TABLE {quote_name(table_name)} ALTER COLUMN {quote_name('exibir_grafico')} SET NOT NULL"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0020_perguntaauditoria_opcoes_resposta_cores"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_exibir_grafico_column, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="perguntaauditoria",
                    name="exibir_grafico",
                    field=models.BooleanField(
                        default=True,
                        help_text="Controla se esta pergunta pode aparecer em relatórios com gráfico.",
                        verbose_name="Exibir gráfico",
                    ),
                ),
            ],
        ),
    ]