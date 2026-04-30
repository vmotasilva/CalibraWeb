import os
import re
import sys
from dataclasses import dataclass


SENSITIVE_NAME_RE = re.compile(
    r"(delete|delet|remov|exclu|apaga|create|novo|new|edit|update|salvar|import|export|download|upload)",
    re.IGNORECASE,
)

SKIP_PREFIXES = (
    "admin:",
    "calibra_admin:",
    "two_factor:",
)


def _ensure_django():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django  # noqa: WPS433

    django.setup()


@dataclass(frozen=True)
class UrlItem:
    view_name: str
    pattern: str


def _iter_urlpatterns(patterns, namespaces=None, prefix=""):
    from django.urls.resolvers import URLPattern, URLResolver  # noqa: WPS433

    namespaces = list(namespaces or [])

    for entry in patterns:
        if isinstance(entry, URLPattern):
            if not entry.name:
                continue
            view_name = ":".join([*namespaces, entry.name]) if namespaces else entry.name
            yield UrlItem(view_name=view_name, pattern=prefix + str(entry.pattern))
        elif isinstance(entry, URLResolver):
            next_namespaces = namespaces
            if entry.namespace:
                next_namespaces = [*namespaces, entry.namespace]
            yield from _iter_urlpatterns(
                entry.url_patterns,
                namespaces=next_namespaces,
                prefix=prefix + str(entry.pattern),
            )


def _get_all_view_names():
    from django.urls import get_resolver  # noqa: WPS433

    resolver = get_resolver()
    items = list(_iter_urlpatterns(resolver.url_patterns))

    # Deduplicate while keeping first-seen pattern
    seen = set()
    result = []
    for item in items:
        if item.view_name in seen:
            continue
        seen.add(item.view_name)
        result.append(item)
    return result


def _get_nav_map():
    from shared.permissions import VIEW_NAME_TO_PERMISSION  # noqa: WPS433

    return VIEW_NAME_TO_PERMISSION


def main() -> int:
    _ensure_django()

    nav_map = _get_nav_map()
    all_items = _get_all_view_names()

    missing_sensitive = []
    for item in all_items:
        if item.view_name in nav_map:
            continue
        if not SENSITIVE_NAME_RE.search(item.view_name):
            continue
        # Skip admin/third-party namespaces
        if item.view_name.startswith(SKIP_PREFIXES):
            continue
        missing_sensitive.append(item)

    missing_sensitive.sort(key=lambda it: it.view_name)

    print("Missing sensitive view_name mappings (not in NAV_STRUCTURE):")
    if not missing_sensitive:
        print("- None")
        return 0

    for item in missing_sensitive:
        print(f"- {item.view_name:45}  {item.pattern}")

    print(f"\nTotal: {len(missing_sensitive)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
