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

def get_user_inbox_items(user: Any, is_global: bool = False) -> list[InboxItem]:
    """Retorna uma lista individual de pendências reais para formar a Inbox."""
    if not getattr(user, "is_authenticated", False):
        return []
        
    cache_key = f"inbox_items:v1:user:{getattr(user, 'pk', 'anon')}:global:{is_global}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    items: list[InboxItem] = []
    hoje = date.today()
    is_global_viewer = is_global and _is_global_viewer(user)
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
                                url=reverse("auditoria:selecionar_modelo_preenchimento"),
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
        if has_module_access(user, "boards") and has_view_access(user, "boards:dashboard"):
            from boards.models import Card, BoardMention, BoardNotification
            from django.db.models import Q
            
            # 4.1 Cartões Atrasados
            cards_vencidos = Card.objects.filter(
                coluna__quadro__arquivado=False,
                data_conclusao__isnull=True,
                data_entrega__lt=hoje
            )
            
            if not is_global_viewer:
                cards_vencidos = cards_vencidos.filter(responsaveis=colaborador).distinct()
                
            for card in cards_vencidos:
                if not card.data_entrega:
                    continue
                dias = (hoje - card.data_entrega).days
                items.append(
                    InboxItem(
                        id=f"card_{card.id}",
                        title=f"A tarefa '{card.titulo}' do quadro '{card.coluna.quadro.nome}' está atrasada há {dias} dias",
                        description=f"Vencida em {card.data_entrega.strftime('%d/%m/%Y')}",
                        module="quadros",
                        icon="bi-kanban",
                        url=f"{reverse('boards:board_detail', args=[card.coluna.quadro.id])}?card_id={card.id}",
                        action_text="Ver Card",
                        date=card.data_entrega,
                        is_urgent=dias > 5
                    )
                )
                
            # 4.2 Marcações não lidas
            if colaborador:
                mencoes = BoardMention.objects.filter(mencionado=colaborador, visualizada=False)
                for mencao in mencoes:
                    items.append(
                        InboxItem(
                            id=f"mention_{mencao.id}",
                            title=f"Você foi mencionado em um comentário na tarefa '{mencao.comentario.cartao.titulo}' do quadro '{mencao.comentario.cartao.coluna.quadro.nome}'",
                            description=f"Por {mencao.criado_por.nome_completo if mencao.criado_por else 'Sistema'}",
                            module="quadros",
                            icon="bi-at",
                            url=reverse("boards:read_mention", args=[mencao.id]),
                            action_text="Ler",
                            date=mencao.criado_em.date(),
                            is_urgent=False
                        )
                    )
            # 4.3 Notificações passivas (alterações no cartão)
            if colaborador:
                notificacoes = BoardNotification.objects.filter(colaborador=colaborador, lida=False)
                for notif in notificacoes:
                    items.append(
                        InboxItem(
                            id=f"notif_{notif.id}",
                            title=f"A tarefa '{notif.cartao.titulo}' do quadro '{notif.cartao.coluna.quadro.nome}' {notif.mensagem} por {notif.criado_por.nome_completo if notif.criado_por else 'Sistema'}",
                            description=f"Alteração passiva",
                            module="quadros",
                            icon="bi-bell",
                            url=reverse("boards:read_board_notification", args=[notif.id]),
                            action_text="Ver Card",
                            date=notif.criado_em.date(),
                            is_urgent=False
                        )
                    )
    except Exception as e:
        print(f"Erro no inbox quadros: {e}")
        pass

    # Sort items: oldest date first (most urgent)
    items.sort(key=lambda x: x.date if x.date else date.max)

    cache.set(cache_key, items, timeout=30)  # Short cache
    return items
