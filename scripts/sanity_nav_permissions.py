import os
import sys


def _ensure_django():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django  # noqa: WPS433

    django.setup()


def _get_perm(codename: str):
    from django.contrib.auth.models import Permission  # noqa: WPS433

    return Permission.objects.get(content_type__app_label="core", codename=codename)


def _reset_user(username: str):
    from django.contrib.auth import get_user_model  # noqa: WPS433

    User = get_user_model()
    User.objects.filter(username=username).delete()
    user = User.objects.create_user(username=username, password="test123")
    user.is_staff = False
    user.is_superuser = False
    user.save(update_fields=["is_staff", "is_superuser"])
    return user


def _render(template_name: str, user):
    from django.template.loader import render_to_string  # noqa: WPS433
    from django.test import RequestFactory  # noqa: WPS433

    request = RequestFactory().get("/")
    request.user = user

    return render_to_string(
        template_name,
        {
            "user": user,
            "colaborador": None,
            "nav_notifications_total": 0,
        },
        request=request,
    )


def _assert_contains(html: str, needle: str, label: str):
    if needle not in html:
        raise AssertionError(f"Expected to contain {label}: {needle!r}")


def _assert_not_contains(html: str, needle: str, label: str):
    if needle in html:
        raise AssertionError(f"Expected NOT to contain {label}: {needle!r}")


def main() -> int:
    _ensure_django()

    templates = [
        "base_desktop.html",
        "base_mobile.html",
    ]

    # Strings específicas do menu (evita falso positivo)
    metrologia_marker = 'data-tooltip="Metrologia"'
    lista_instrumentos_marker = "📋 Lista de Instrumentos"
    gestao_header_marker = "GESTÃO"

    procedimentos_marker = "Procedimentos"  # item no menu mobile

    results: list[str] = []

    # 1) Usuário sem perms: não deve ver Metrologia nem Procedimentos
    user_none = _reset_user("sanity_nav_none")
    for tpl in templates:
        html = _render(tpl, user_none)
        _assert_not_contains(html, metrologia_marker, f"{tpl} Metrologia")
        if tpl == "base_mobile.html":
            _assert_not_contains(html, procedimentos_marker, f"{tpl} Procedimentos")
    results.append("PASS: usuário sem perms não vê módulos")

    # 2) Metrologia módulo ON, mas sem blocos/funções: mostra Metrologia, mas não mostra itens do bloco
    user_met_mod = _reset_user("sanity_nav_met_mod")
    user_met_mod.user_permissions.add(_get_perm("nav_mod_metrologia"))
    for tpl in templates:
        html = _render(tpl, user_met_mod)
        _assert_contains(html, metrologia_marker, f"{tpl} Metrologia")
        _assert_not_contains(html, lista_instrumentos_marker, f"{tpl} Lista de Instrumentos")
        _assert_not_contains(html, gestao_header_marker, f"{tpl} header GESTÃO")
    results.append("PASS: módulo sozinho não mostra blocos/itens")

    # 3) Metrologia gestão + lista instrumentos: deve aparecer
    user_met_full = _reset_user("sanity_nav_met_full")
    user_met_full.user_permissions.add(_get_perm("nav_mod_metrologia"))
    user_met_full.user_permissions.add(_get_perm("nav_metrologia_gestao"))
    user_met_full.user_permissions.add(_get_perm("nav_metrologia_lista_instrumentos"))
    for tpl in templates:
        html = _render(tpl, user_met_full)
        _assert_contains(html, metrologia_marker, f"{tpl} Metrologia")
        _assert_contains(html, lista_instrumentos_marker, f"{tpl} Lista de Instrumentos")
    results.append("PASS: metrologia gestão/lista aparece")

    # 4) Procedimentos (mobile) só aparece com a permissão da view
    user_proc = _reset_user("sanity_nav_proc")
    user_proc.user_permissions.add(_get_perm("nav_treinamentos_procedimentos"))
    html_mobile = _render("base_mobile.html", user_proc)
    _assert_contains(html_mobile, procedimentos_marker, "mobile Procedimentos")
    results.append("PASS: procedimentos aparece no mobile quando permitido")

    print("\n".join(results))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        raise
