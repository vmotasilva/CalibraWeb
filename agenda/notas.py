"""Comentários e ocorrências do preenchimento do Meu checklist."""
from collections import Counter

from agenda.models import ChecklistItem, CompartilhadoTarefa, ComentarioChecklist, Evento, OcorrenciaChecklist
from agenda.services import checklists_diarios, ocorrencias

TIPOS = ("item", "tarefa", "evento")


def resolver_ref(user, tipo, ref_id, dia):
    """Confere que o item (`tipo` = item/tarefa/evento) faz parte da folha do usuário em `dia`.

    Devolve {"campo": "item"|"tarefa"|"evento", "obj", "checklist_titulo", "item_texto"} ou None.
    """
    if tipo not in TIPOS or not str(ref_id or "").isdigit():
        return None
    ref_id = int(ref_id)
    if tipo == "item":
        for o in checklists_diarios(user, dia, dia) + ocorrencias(user, dia, dia, so_checklist=True):
            for i in o["itens"]:
                if i["id"] == ref_id:
                    item = ChecklistItem.objects.filter(pk=ref_id).first()
                    return {"campo": "item", "obj": item, "checklist_titulo": o["titulo"], "item_texto": i["texto"]} if item else None
        return None
    if tipo == "evento":  # evento com checklist simples (sem itens): o próprio evento é o item
        for o in ocorrencias(user, dia, dia, so_checklist=True):
            if o["id"] == ref_id and not o["itens"]:
                ev = Evento.objects.filter(pk=ref_id).first()
                return {"campo": "evento", "obj": ev, "checklist_titulo": "Agenda", "item_texto": o["titulo"]} if ev else None
        return None
    t = CompartilhadoTarefa.objects.select_related("lista").filter(pk=ref_id, lista__membros__usuario=user).first()
    if not t:
        return None
    return {"campo": "tarefa", "obj": t, "checklist_titulo": t.lista.titulo, "item_texto": t.texto}


def anotar_contagens(user, itens_dia, compartilhados, pendencias):
    """Põe `n_coment` e `n_ocorr` em cada item exibido (para os ícones da tela): itens do dia, compartilhados e pendências."""
    chaves = []  # (tipo, id, data, dict)
    for o in itens_dia:
        if o["itens"]:
            chaves += [("item", i["id"], o["dia"], i) for i in o["itens"]]
        else:
            chaves.append(("evento", o["id"], o["dia"], o))
    for t in compartilhados:
        chaves.append(("tarefa", t["id"], t.get("dia"), t))
    for p in pendencias:
        chaves += [("item", i["id"], p["dia"], i) if i["id"] else ("evento", p["id"], p["dia"], i) for i in p["faltam"]]
    datas = {d for _, _, d, _ in chaves if d}
    if not chaves:
        return
    comentarios, ocorrs = Counter(), Counter()
    for item_id, tarefa_id, evento_id, data in ComentarioChecklist.objects.filter(usuario=user, data__in=datas).values_list(
        "item_id", "tarefa_id", "evento_id", "data"
    ):
        comentarios[(_tipo(item_id, tarefa_id, evento_id), item_id or tarefa_id or evento_id, data)] += 1
    for item_id, tarefa_id, evento_id, data in OcorrenciaChecklist.objects.filter(criado_por=user, data__in=datas).values_list(
        "item_id", "tarefa_id", "evento_id", "data"
    ):
        ocorrs[(_tipo(item_id, tarefa_id, evento_id), item_id or tarefa_id or evento_id, data)] += 1
    for tipo, ref, data, alvo in chaves:
        alvo["n_coment"], alvo["n_ocorr"] = comentarios[(tipo, ref, data)], ocorrs[(tipo, ref, data)]


def _tipo(item_id, tarefa_id, evento_id):
    return "item" if item_id else "tarefa" if tarefa_id else "evento"
