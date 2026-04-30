from django.db import migrations, models
import unicodedata


DEFAULT_GREEN = "#198754"
DEFAULT_RED = "#dc3545"


def _normalize_label(value: str) -> str:
    s = str(value or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())


def _parse_options(raw: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for line in str(raw or "").replace("\r\n", "\n").split("\n"):
        label = line.strip()
        if not label:
            continue
        key = _normalize_label(label)
        if key in seen:
            continue
        seen.add(key)
        values.append(label)
    return values


def forwards_populate_option_colors(apps, schema_editor):
    PerguntaAuditoria = apps.get_model("auditoria", "PerguntaAuditoria")

    for pergunta in PerguntaAuditoria.objects.all().iterator():
        color_map = {}

        if pergunta.tipo_resposta == "SIM_NAO":
            color_map = {
                "Sim": DEFAULT_GREEN,
                "Não": DEFAULT_RED,
            }
        elif pergunta.tipo_resposta == "LISTA":
            for opt in _parse_options(pergunta.opcoes_resposta):
                key = _normalize_label(opt)
                if key == "conforme":
                    color_map[opt] = DEFAULT_GREEN
                elif key == "nao conforme":
                    color_map[opt] = DEFAULT_RED
                # N/A permanece sem cor.

        if color_map:
            pergunta.opcoes_resposta_cores = color_map
            pergunta.save(update_fields=["opcoes_resposta_cores"])


def backwards_clear_option_colors(apps, schema_editor):
    PerguntaAuditoria = apps.get_model("auditoria", "PerguntaAuditoria")
    PerguntaAuditoria.objects.update(opcoes_resposta_cores={})


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0019_relatoriocompartilhadoauditoria"),
    ]

    operations = [
        migrations.AddField(
            model_name="perguntaauditoria",
            name="opcoes_resposta_cores",
            field=models.JSONField(blank=True, default=dict, help_text="Mapa de cores por opção (hex), usado em tipo Lista e Sim/Não.", verbose_name="Cores das opções"),
        ),
        migrations.RunPython(forwards_populate_option_colors, backwards_clear_option_colors),
    ]
