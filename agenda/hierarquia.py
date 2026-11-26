"""Hierarquia da Agenda: líderes ajustam e vistoriam as agendas e checklists dos liderados.

A cadeia vem dos vínculos do cadastro de pessoas (rh.Colaborador): `lider`, `vice_lider`, `supervisor`
e `gerente`. Quem aparece num desses campos de um colaborador é chefia direta dele, com o respectivo papel.
"""
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

# do maior para o menor: se a mesma pessoa tem mais de um papel sobre o liderado, mostra o maior
PAPEIS = (("gerente", "Gerente"), ("supervisor", "Supervisor"), ("lider", "Líder"), ("vice_lider", "Vice-Líder"))


def colaborador_do_usuario(user):
    from rh.models import Colaborador

    if not getattr(user, "is_authenticated", False):
        return None
    return Colaborador.objects.filter(user_django=user, is_active=True).first()


def equipe_de(user):
    """Liderados (com login) do usuário: lista de dicts {usuario, colaborador, papel}, ordenada por nome.

    Superusuário enxerga todos os colaboradores ativos com login (papel "Administrador").
    """
    from rh.models import Colaborador

    base = Colaborador.objects.filter(is_active=True, user_django__isnull=False, user_django__is_active=True)
    if user.is_superuser:
        qs = base.exclude(user_django=user)
        papeis = {}
    else:
        me = colaborador_do_usuario(user)
        if not me:
            return []
        qs = base.filter(Q(lider=me) | Q(vice_lider=me) | Q(supervisor=me) | Q(gerente=me)).exclude(pk=me.pk)
        papeis = None
    saida = []
    for c in qs.select_related("user_django", "setor").order_by("nome_completo"):
        if papeis is None:
            papel = next((rot for campo, rot in PAPEIS if getattr(c, f"{campo}_id") == me.pk), "")
        else:
            papel = "Administrador"
        saida.append({"usuario": c.user_django, "colaborador": c, "papel": papel})
    return saida


def liderados_ids(user):
    """Ids dos liderados; guardado no objeto `user` (vive uma requisição) para não repetir a consulta."""
    cache = getattr(user, "_agenda_liderados_ids", None)
    if cache is None:
        cache = {m["usuario"].pk for m in equipe_de(user)}
        user._agenda_liderados_ids = cache
    return cache


def pode_gerir(user, alvo):
    """True se `user` pode ver e ajustar a agenda/checklists de `alvo`: o próprio, superusuário ou chefia dele."""
    if user.pk == alvo.pk or user.is_superuser:
        return True
    return alvo.pk in liderados_ids(user)


def papel_sobre(user, alvo):
    if user.pk == alvo.pk:
        return ""
    for m in equipe_de(user):
        if m["usuario"].pk == alvo.pk:
            return m["papel"]
    return ""


def nome_do_usuario(user):
    c = colaborador_do_usuario(user)
    return (c.nome_completo if c else None) or user.get_full_name() or user.username
