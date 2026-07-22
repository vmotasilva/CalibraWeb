from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from django.urls import reverse
from django.core.cache import cache
from shared.notifications import _is_global_viewer, _get_colaborador_for_user

@dataclass
class InboxItem:
    id: str                 # Unique ID for UI tracking (module_id)
    title: str              # Title of the task
    description: str        # Details
    module: str             # "auditoria", "metrologia", "cotacoes", "quadros", "treinamentos"
    icon: str               # Bootstrap icon class
    url: str                # Where to click to resolve
    action_text: str        # Text for the button
    date: date              # For sorting (oldest first)
    is_urgent: bool = False # Flag for highlighting very old tasks

def get_user_inbox_items(user: Any) -> list[InboxItem]:
    """Retorna uma lista individual de pendências reais para formar a Inbox."""
    if not getattr(user, "is_authenticated", False):
        return []
        
    cache_key = f"inbox_items:v1:user:{getattr(user, 'pk', 'anon')}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    items: list[InboxItem] = []
    hoje = date.today()
    is_global_viewer = _is_global_viewer(user)
    colaborador = _get_colaborador_for_user(user)
    
    from shared.permissions import has_module_access, has_view_access

    # 1. Auditoria
    try:
        if has_module_access(user, "auditoria") and has_view_access(user, "auditoria:modulo"):
            from auditoria.models import ModeloAuditoria
            from django.db.models import Q
            from auditoria.utils_periodos import calcular_periodos_pendentes
            
            modelos = ModeloAuditoria.objects.filter(ativo=True)
            if not is_global_viewer:
                modelos = modelos.filter(Q(responsavel=user) | Q(responsaveis=user)).distinct()
                
            for modelo in modelos:
                # Retorna no máximo 3 por modelo para não explodir a inbox se estiver muito atrasado
                periodos = calcular_periodos_pendentes(modelo, limit=3)
                for p in periodos:
                    fim_date = p.get('fim_date')
                    if fim_date:
                        items.append(
                            InboxItem(
                                id=f"auditoria_{modelo.id}_{fim_date.isoformat()}",
                                title=f"Preencher Auditoria: {modelo.nome}",
                                description=f"Período atrasado: {p['label']}",
                                module="auditoria",
                                icon="bi-clipboard-check",
                                url=reverse("auditoria:registro_create_modelo", args=[modelo.id]),
                                action_text="Preencher",
                                date=fim_date,
                                is_urgent=(hoje - fim_date).days > 30
                            )
                        )
    except Exception as e:
        pass

    # 2. Metrologia
    try:
        if has_module_access(user, "metrologia") and has_view_access(user, "metrologia:modulo_metrologia"):
            from metrologia.models import Instrumento
            from django.db.models import Q

            global_vencidos = Instrumento.objects.filter(
                ativo=True,
                data_proxima_calibracao__lt=hoje,
            )
            
            if not is_global_viewer and colaborador:
                global_vencidos = global_vencidos.filter(
                    Q(responsavel=colaborador) | Q(responsavel__isnull=True)
                )

            for inst in global_vencidos:
                dias_atraso = (hoje - inst.data_proxima_calibracao).days if inst.data_proxima_calibracao else 0
                items.append(
                    InboxItem(
                        id=f"metrologia_{inst.id}",
                        title=f"Calibração Vencida: {inst.codigo or inst.nome}",
                        description=f"{inst.nome} venceu em {inst.data_proxima_calibracao.strftime('%d/%m/%Y')} ({dias_atraso} dias de atraso)",
                        module="metrologia",
                        icon="bi-tools",
                        url=reverse("metrologia:instrumento_detail", args=[inst.id]),
                        action_text="Calibrar",
                        date=inst.data_proxima_calibracao,
                        is_urgent=dias_atraso > 15
                    )
                )
    except Exception:
        pass

    # 3. Cotações (Metrologia novo fluxo)
    try:
        if has_module_access(user, "metrologia") and has_view_access(user, "metrologia:solicitacao_list"):
            from metrologia.models import SolicitacaoCotacao

            solicitacoes = SolicitacaoCotacao.objects.exclude(status__in=["CONCLUIDA", "CANCELADA"]).filter(
                data_solicitacao_orcamento__isnull=False,
                data_solicitacao_orcamento__lte=hoje,
            )
            if not is_global_viewer:
                solicitacoes = solicitacoes.filter(responsavel=user)

            for sol in solicitacoes:
                items.append(
                    InboxItem(
                        id=f"cotacao_{sol.id}",
                        title=f"Cotação Atrasada: Solicitação #{sol.id}",
                        description=f"Prazo venceu em {sol.data_solicitacao_orcamento.strftime('%d/%m/%Y')}",
                        module="cotacoes",
                        icon="bi-cash-coin",
                        url=reverse("metrologia:solicitacao_detail", args=[sol.id]),
                        action_text="Resolver",
                        date=sol.data_solicitacao_orcamento,
                        is_urgent=(hoje - sol.data_solicitacao_orcamento).days > 7
                    )
                )
    except Exception:
        pass

    # 4. Quadros (Kanban)
    try:
        if has_module_access(user, "quadros") and has_view_access(user, "quadros:quadros_list"):
            from quadros.models import Card
            from django.db.models import Q
            
            cards_vencidos = Card.objects.filter(
                quadro__ativo=True,
                status="ATIVO",
                prazo__lt=hoje
            )
            
            if not is_global_viewer:
                cards_vencidos = cards_vencidos.filter(Q(responsaveis=user) | Q(criado_por=user)).distinct()
                
            for card in cards_vencidos:
                dias = (hoje - card.prazo).days
                items.append(
                    InboxItem(
                        id=f"card_{card.id}",
                        title=f"Card Atrasado: {card.titulo}",
                        description=f"Quadro: {card.quadro.nome} - Venceu há {dias} dias",
                        module="quadros",
                        icon="bi-kanban",
                        url=reverse("quadros:card_detail", args=[card.id]),
                        action_text="Ver Card",
                        date=card.prazo,
                        is_urgent=dias > 5
                    )
                )
    except Exception:
        pass

    # Sort items: oldest date first (most urgent)
    items.sort(key=lambda x: x.date if x.date else date.max)

    cache.set(cache_key, items, timeout=30)  # Short cache
    return items
