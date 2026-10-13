from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from shared.permissions import (
    NAV_STRUCTURE,
    _nav_module_config,
    _user_has_nav_perm,
    has_module_access,
)


class Command(BaseCommand):
    help = (
        "Lista usuários que perderiam acesso ao ativar PERMISSIONS_ENFORCEMENT=enforce: "
        "têm permissões de função num módulo mas não têm o módulo ('No menu') nem o grupo legado."
    )

    def handle(self, *args, **opts):
        User = get_user_model()
        total = 0
        for user in User.objects.filter(is_active=True, is_superuser=False, is_staff=False).order_by("username"):
            problemas = []
            for key in [m.get("key") for m in NAV_STRUCTURE]:
                cfg = _nav_module_config(key)
                if not cfg or not cfg.get("module_perm") or has_module_access(user, key):
                    continue
                funcoes = [
                    f["perm"]
                    for b in cfg.get("blocos") or []
                    for f in b.get("funcoes") or []
                    if f.get("perm") and f.get("view_name") and _user_has_nav_perm(user, f["perm"])
                ]
                if funcoes:
                    problemas.append(f"{key}: {len(funcoes)} função(ões) sem o módulo")
            if problemas:
                total += 1
                self.stdout.write(f"{user.username}: " + "; ".join(problemas))
        self.stdout.write(self.style.SUCCESS(f"{total} usuário(s) seriam afetados."))
