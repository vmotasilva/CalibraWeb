from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
from shared.notifications import _is_global_viewer, _get_colaborador_for_user

@dataclass
class InboxItem:
    id: str                 # Unique ID for UI tracking (module_id)
    title: str              # Title of the task
    description: str        # Details
    module: str             # "Auditoria", "Metrologia", "Quadros", "Treinamentos", "Laboratório", etc.
    icon: str               # Bootstrap icon class
    url: str                # Where to click to resolve
    action_text: str        # Text for the button
    date: date              # For sorting (oldest first)
    is_urgent: bool = False # Flag for highlighting very old tasks
    sub_type: str = ""      # "Demanda por Liderança", "Demanda por Instrutor", "Avaliação de Eficácia", "Atualização de Matriz de Habilidade", etc.

def get_user_inbox_items(user: Any, is_global: bool = False) -> list[InboxItem]:
    """Retorna uma lista individual de pendências reais para formar a Inbox e as Notificações por Origem."""
    if not getattr(user, "is_authenticated", False):
        return []
        
    cache_key = f"inbox_items:v4:user:{getattr(user, 'pk', 'anon')}:global:{is_global}"
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
        if has_module_access(user, "auditoria") or user.is_superuser or user.is_staff or getattr(user, "is_authenticated", False):
            from auditoria.models import ModeloAuditoria, RelatorioCompartilhadoAuditoria
            from django.db.models import Q
            from auditoria.utils_periodos import calcular_periodos_pendentes
            from urllib.parse import urlencode
            
            # 1.1 Ciclos / Modelos com períodos atrasados
            modelos = ModeloAuditoria.objects.filter(ativo=True)
            if not is_global_viewer and not (user.is_superuser or user.is_staff):
                scoped_modelos = modelos.filter(Q(responsavel=user) | Q(responsaveis=user)).distinct()
                target_modelos = scoped_modelos if scoped_modelos.exists() else modelos
            else:
                target_modelos = modelos
                
            for modelo in target_modelos:
                periodos = calcular_periodos_pendentes(modelo, limit=3)
                for p in periodos:
                    fim_date = p.get('fim_date')
                    if fim_date:
                        items.append(
                            InboxItem(
                                id=f"auditoria_{modelo.id}_{fim_date.isoformat()}",
                                title=f"Preencher Auditoria: {modelo.nome}",
                                description=f"Período atrasado: {p['label']}",
                                module="Auditoria",
                                icon="bi-clipboard-check",
                                url=reverse("auditoria:selecionar_modelo_preenchimento"),
                                action_text="Preencher",
                                date=fim_date,
                                is_urgent=(hoje - fim_date).days > 30,
                                sub_type="Períodos em Atraso"
                            )
                        )
            
            # 1.2 Relatórios Compartilhados Pendentes de Leitura
            now = timezone.now()
            shares_qs = RelatorioCompartilhadoAuditoria.objects.filter(
                destinatario=user, ativo=True, recebido_em__isnull=True
            ).filter(Q(expira_em__isnull=True) | Q(expira_em__gt=now)).select_related("remetente", "modelo")
            for s in shares_qs:
                target = reverse("auditoria:registros_por_modelo_compartilhado", args=[s.modelo_id])
                url = f"{target}?{urlencode({'share_token': s.token})}"
                items.append(
                    InboxItem(
                        id=f"auditoria_share_{s.id}",
                        title=f"Relatório Compartilhado: {s.modelo.nome}",
                        description=f"Enviado por {s.remetente.username if s.remetente else 'Auditor'}",
                        module="Auditoria",
                        icon="bi-file-earmark-bar-graph",
                        url=url,
                        action_text="Visualizar",
                        date=s.criado_em.date(),
                        is_urgent=False,
                        sub_type="Relatórios Compartilhados"
                    )
                )
    except Exception:
        pass

    # 2. Metrologia - Calibrações Vencidas
    try:
        if has_module_access(user, "metrologia") or user.is_superuser or user.is_staff or getattr(user, "is_authenticated", False):
            from metrologia.models import Instrumento
            from django.db.models import Q

            global_vencidos = Instrumento.objects.filter(
                ativo=True,
                data_proxima_calibracao__lt=hoje,
            ).select_related('responsavel')
            
            if not is_global_viewer and colaborador and not (user.is_superuser or user.is_staff):
                scoped_vencidos = global_vencidos.filter(
                    Q(responsavel=colaborador) | Q(responsavel__isnull=True)
                )
                target_vencidos = scoped_vencidos if scoped_vencidos.exists() else global_vencidos
            else:
                target_vencidos = global_vencidos

            for inst in target_vencidos[:100]:
                dias_atraso = (hoje - inst.data_proxima_calibracao).days if inst.data_proxima_calibracao else 0
                try:
                    target_url = reverse("detalhe_instrumento", args=[inst.id])
                except Exception:
                    try:
                        target_url = reverse("visualizar_instrumento", args=[inst.id])
                    except Exception:
                        target_url = "/metrologia/"

                items.append(
                    InboxItem(
                        id=f"metrologia_{inst.id}",
                        title=f"Calibração Vencida: {inst.tag or inst.codigo or ('ID ' + str(inst.id))}",
                        description=f"{inst.descricao or inst.tag} venceu em {inst.data_proxima_calibracao.strftime('%d/%m/%Y')} ({dias_atraso} dias de atraso)",
                        module="Metrologia",
                        icon="bi-tools",
                        url=target_url,
                        action_text="Calibrar",
                        date=inst.data_proxima_calibracao,
                        is_urgent=dias_atraso > 15,
                        sub_type="Calibrações Vencidas"
                    )
                )
    except Exception:
        pass

    # 3. Metrologia - Cotações em Atraso
    try:
        if has_module_access(user, "metrologia") or user.is_superuser or user.is_staff or getattr(user, "is_authenticated", False):
            from metrologia.models import SolicitacaoCotacao

            solicitacoes = SolicitacaoCotacao.objects.exclude(status__in=["CONCLUIDA", "CANCELADA"]).filter(
                data_solicitacao_orcamento__isnull=False,
                data_solicitacao_orcamento__lte=hoje,
            )
            if not is_global_viewer and not (user.is_superuser or user.is_staff):
                scoped_sol = solicitacoes.filter(responsavel=user)
                target_sol = scoped_sol if scoped_sol.exists() else solicitacoes
            else:
                target_sol = solicitacoes

            for sol in target_sol[:20]:
                try:
                    target_url = reverse("metrologia:solicitacao_detail", args=[sol.id])
                except Exception:
                    target_url = "/metrologia/solicitacoes/"

                items.append(
                    InboxItem(
                        id=f"cotacao_{sol.id}",
                        title=f"Cotação Atrasada: Solicitação #{sol.id}",
                        description=f"Prazo venceu em {sol.data_solicitacao_orcamento.strftime('%d/%m/%Y')}",
                        module="Metrologia",
                        icon="bi-cash-coin",
                        url=target_url,
                        action_text="Resolver",
                        date=sol.data_solicitacao_orcamento,
                        is_urgent=(hoje - sol.data_solicitacao_orcamento).days > 7,
                        sub_type="Cotações Atrasadas"
                    )
                )
    except Exception:
        pass

    # 4. Metrologia - Ocorrências em Aberto
    try:
        if has_module_access(user, "metrologia") or user.is_superuser or user.is_staff or getattr(user, "is_authenticated", False):
            from qms.models import OcorrenciaInstrumento

            ocorrencias_abertas = OcorrenciaInstrumento.objects.filter(
                status="ABERTA"
            ).select_related("instrumento", "usuario_responsavel").order_by("-data_ocorrencia")

            for oc in ocorrencias_abertas[:50]:
                inst = oc.instrumento
                inst_tag = (inst.tag or inst.codigo or f"ID {inst.id}") if inst else "Instrumento Não Identificado"
                inst_desc = f"{inst.descricao} — " if inst and inst.descricao else ""
                tipo_nome = oc.get_tipo_display() if hasattr(oc, 'get_tipo_display') else oc.tipo
                
                try:
                    if inst:
                        target_url = reverse("detalhe_instrumento", args=[inst.id])
                    else:
                        target_url = "/metrologia/"
                except Exception:
                    try:
                        if inst:
                            target_url = reverse("visualizar_instrumento", args=[inst.id])
                        else:
                            target_url = "/metrologia/"
                    except Exception:
                        target_url = "/metrologia/"

                data_oc = oc.data_ocorrencia or hoje
                items.append(
                    InboxItem(
                        id=f"ocorrencia_{oc.id}",
                        title=f"Ocorrência Aberta ({tipo_nome}): {inst_tag}",
                        description=f"{inst_desc}{oc.descricao}",
                        module="Metrologia",
                        icon="bi-exclamation-octagon",
                        url=target_url,
                        action_text="Resolver",
                        date=data_oc,
                        is_urgent=True,
                        sub_type="Ocorrências em Aberto"
                    )
                )
    except Exception:
        pass

    # 4. Quadros (Kanban)
    try:
        if has_module_access(user, "boards"):
            from boards.models import Card, BoardNotification, BoardMention
            from django.db.models import Q

            # 4.1 Tarefas Atrasadas Atribuídas ao Usuário
            if colaborador:
                meus_cartoes_atrasados = Card.objects.filter(
                    coluna__board__arquivado=False,
                    responsaveis=colaborador,
                    data_entrega__lt=hoje,
                    data_conclusao__isnull=True
                ).select_related("coluna__board")

                for card in meus_cartoes_atrasados:
                    dias = (hoje - card.data_entrega).days
                    items.append(
                        InboxItem(
                            id=f"board_card_{card.id}",
                            title=f"Tarefa Atrasada: {card.titulo}",
                            description=f"Quadro: {card.coluna.board.nome} (Venceu há {dias} dias)",
                            module="Quadros",
                            icon="bi-kanban",
                            url=f"{reverse('boards:board_detail', args=[card.coluna.board.id])}?card={card.id}",
                            action_text="Abrir Card",
                            date=card.data_entrega,
                            is_urgent=dias > 7,
                            sub_type="Tarefas Atrasadas"
                        )
                    )

            # 4.2 Menções não lidas
            mencoes_nao_lidas = BoardMention.objects.filter(
                mencionado=colaborador,
                visualizada=False
            ).select_related("card__coluna__board")[:15] if colaborador else []

            for mention in mencoes_nao_lidas:
                if mention.card:
                    items.append(
                        InboxItem(
                            id=f"board_mention_{mention.id}",
                            title=f"Você foi mencionado em: {mention.card.titulo}",
                            description=f"No quadro {mention.card.coluna.board.nome}",
                            module="Quadros",
                            icon="bi-at",
                            url=f"{reverse('boards:board_detail', args=[mention.card.coluna.board.id])}?card={mention.card.id}",
                            action_text="Ver Menção",
                            date=mention.criado_em.date(),
                            is_urgent=False,
                            sub_type="Menções Não Lidas"
                        )
                    )

            # 4.3 Notificações de cartões
            notificacoes_boards = BoardNotification.objects.filter(
                usuario=user,
                lida=False
            ).select_related("card__coluna__board")[:15]

            for notif in notificacoes_boards:
                if notif.card:
                    items.append(
                        InboxItem(
                            id=f"board_notif_{notif.id}",
                            title=notif.mensagem,
                            description=f"Quadro: {notif.card.coluna.board.nome}",
                            module="Quadros",
                            icon="bi-bell-fill",
                            url=reverse("boards:read_board_notification", args=[notif.id]),
                            action_text="Ver Card",
                            date=notif.criado_em.date(),
                            is_urgent=False,
                            sub_type="Notificações do Quadro"
                        )
                    )
    except Exception:
        pass

    # 5. Treinamentos (Procedimentos, Avaliações de Eficácia, Demandas e Planejamentos)
    try:
        if has_module_access(user, "procedures") or has_module_access(user, "treinamentos") or user.is_superuser or user.is_staff:
            from procedures.models import RegistroTreinamento, SolicitacaoValidacaoMatriz, PlanejamentoTreinamento
            from datetime import timedelta
            from django.db.models import Q, F

            # 5.1 Avaliação de Eficácia pendente (após 30 dias de elegibilidade)
            data_limite_30d = hoje - timedelta(days=30)
            qs_eficacia = RegistroTreinamento.objects.filter(
                ativo=True,
                procedimento__criticidade="CRITICO",
                data_treinamento__lte=data_limite_30d,
                avaliacao_eficacia_status="PENDENTE",
                colaborador__is_active=True,
                colaborador__afastado=False,
                colaborador__em_ferias=False,
            ).select_related("colaborador", "procedimento", "gestor_responsavel", "colaborador__lider", "colaborador__supervisor", "colaborador__gerente")

            if not is_global_viewer and colaborador and not (user.is_superuser or user.is_staff):
                scoped_eficacia = qs_eficacia.filter(
                    Q(gestor_responsavel=colaborador)
                    | (
                        Q(gestor_responsavel__isnull=True)
                        & (
                            Q(colaborador__lider=colaborador)
                            | Q(colaborador__supervisor=colaborador)
                            | Q(colaborador__gerente=colaborador)
                        )
                    )
                )
                target_eficacia = scoped_eficacia if scoped_eficacia.exists() else qs_eficacia
            else:
                target_eficacia = qs_eficacia

            for t in target_eficacia[:20]:
                dias = (hoje - t.data_treinamento).days
                items.append(
                    InboxItem(
                        id=f"eficacia_{t.id}",
                        title=f"Avaliação de Eficácia: {t.colaborador.nome_completo}",
                        description=f"Treinamento crítico {t.procedimento.codigo} realizado há {dias} dias",
                        module="Treinamentos",
                        icon="bi-mortarboard",
                        url=reverse("procedures:avaliacao_eficacia_list"),
                        action_text="Avaliar",
                        date=t.data_treinamento,
                        is_urgent=dias > 60,
                        sub_type="Avaliação de Eficácia"
                    )
                )

            # 5.2 Demandas de Treinamento Pendentes por Liderança
            pendencias_demanda = (
                Q(data_treinamento__isnull=True)
                | (
                    Q(lista_presenca__isnull=True)
                    & (
                        (
                            Q(procedimento__numero_revisao__isnull=False)
                            & ~Q(revisao_treinada=F("procedimento__numero_revisao"))
                        )
                        | (
                            Q(procedimento__data_aprovacao__isnull=False)
                            & Q(data_treinamento__lt=F("procedimento__data_aprovacao"))
                        )
                    )
                )
            )
            qs_demandas = RegistroTreinamento.objects.filter(
                ativo=True,
                tipo="PROCEDIMENTO",
                procedimento__isnull=False,
                colaborador__is_active=True,
            ).filter(pendencias_demanda).select_related("colaborador", "procedimento")

            if not is_global_viewer and colaborador and not (user.is_superuser or user.is_staff):
                scoped_demandas = qs_demandas.filter(
                    Q(colaborador=colaborador) | Q(colaborador__lider=colaborador) | Q(colaborador__supervisor=colaborador) | Q(colaborador__gerente=colaborador)
                )
                target_demandas = scoped_demandas if scoped_demandas.exists() else qs_demandas
            else:
                target_demandas = qs_demandas

            for d in target_demandas[:20]:
                lider_id = ""
                if d.colaborador and d.colaborador.lider_id:
                    lider_id = str(d.colaborador.lider_id)
                elif colaborador:
                    lider_id = str(colaborador.id)

                target_url = f"{reverse('procedures:dashboard_treinamentos')}?colaborador_id={d.colaborador_id}"
                if lider_id:
                    target_url += f"&lider={lider_id}"

                items.append(
                    InboxItem(
                        id=f"demanda_{d.id}",
                        title=f"Demanda Liderança: {d.colaborador.nome_completo}",
                        description=f"Procedimento {d.procedimento.codigo} pendente de treinamento da equipe",
                        module="Treinamentos",
                        icon="bi-book",
                        url=target_url,
                        action_text="Abrir Painel",
                        date=d.criado_em.date() if hasattr(d, "criado_em") and d.criado_em else hoje,
                        is_urgent=False,
                        sub_type="Demanda por Liderança"
                    )
                )

            # 5.3 Validações de Matriz de Habilidade
            try:
                qs_matriz = SolicitacaoValidacaoMatriz.objects.filter(
                    status="pendente",
                ).select_related("colaborador")
                if not is_global_viewer and colaborador and not (user.is_superuser or user.is_staff):
                    scoped_matriz = qs_matriz.filter(validador=colaborador)
                    target_matriz = scoped_matriz if scoped_matriz.exists() else qs_matriz
                else:
                    target_matriz = qs_matriz

                for v in target_matriz[:10]:
                    items.append(
                        InboxItem(
                            id=f"matriz_{v.id}",
                            title=f"Validação de Matriz: {v.colaborador.nome_completo}",
                            description="Pendente de validação de competências pelo líder",
                            module="Treinamentos",
                            icon="bi-award",
                            url=reverse("procedures:matriz_avaliacoes"),
                            action_text="Validar",
                            date=v.criado_em.date() if hasattr(v, "criado_em") and v.criado_em else hoje,
                            is_urgent=False,
                            sub_type="Atualização de Matriz de Habilidade"
                        )
                    )
            except Exception:
                pass

            # 5.4 Demanda por Instrutor (Responsáveis de Matriz e Planejamentos)
            try:
                from procedures.models import ResponsavelTreinamentoMatriz

                # A. Instrutores Responsáveis por Matriz / Sub-Área
                qs_resp_matriz = ResponsavelTreinamentoMatriz.objects.select_related(
                    "matriz", "sub_area", "colaborador"
                )
                if not is_global_viewer and colaborador and not (user.is_superuser or user.is_staff):
                    qs_resp_matriz = qs_resp_matriz.filter(colaborador=colaborador)

                for rm in qs_resp_matriz[:20]:
                    matriz_nome = rm.matriz.nome if rm.matriz else "Matriz de Procedimentos"
                    sub_nome = f" ({rm.sub_area.nome})" if rm.sub_area else ""
                    target_url = f"{reverse('procedures:dashboard_treinamentos')}?instrutor_responsavel={rm.colaborador_id}&matriz={rm.matriz_id}"
                    if rm.sub_area_id:
                        target_url += f"&sub_area={rm.sub_area_id}"
                    if rm.turno:
                        target_url += f"&turno={rm.turno}"

                    items.append(
                        InboxItem(
                            id=f"resp_matriz_{rm.id}",
                            title=f"Demanda Instrutor: {rm.colaborador.nome_completo}",
                            description=f"{matriz_nome}{sub_nome} - Turno {rm.turno or 'Geral'}",
                            module="Treinamentos",
                            icon="bi-person-video3",
                            url=target_url,
                            action_text="Abrir Painel",
                            date=rm.atualizado_em.date() if rm.atualizado_em else hoje,
                            is_urgent=False,
                            sub_type="Demanda por Instrutor"
                        )
                    )

                # B. Planejamentos de Treinamento
                qs_plan = PlanejamentoTreinamento.objects.filter(
                    status__in=['PLANEJADO', 'EM_ANDAMENTO'],
                    data_planejada__lte=hoje + timedelta(days=7)
                ).select_related('procedimento', 'responsavel')

                if not is_global_viewer and colaborador and not (user.is_superuser or user.is_staff):
                    scoped_plan = qs_plan.filter(responsavel=colaborador)
                    target_plan = scoped_plan if scoped_plan.exists() else qs_plan
                else:
                    target_plan = qs_plan

                for pl in target_plan[:15]:
                    atrasado = bool(pl.data_planejada and pl.data_planejada < hoje)
                    proc_code = pl.procedimento.codigo if pl.procedimento else "Treinamento"
                    instrutor_id = pl.responsavel_id or (colaborador.id if colaborador else "")
                    target_url = f"{reverse('procedures:dashboard_treinamentos')}?instrutor_responsavel={instrutor_id}" if instrutor_id else reverse('procedures:dashboard_treinamentos')

                    items.append(
                        InboxItem(
                            id=f"planejamento_{pl.id}",
                            title=f"Demanda Instrutor: {proc_code}",
                            description=f"{'Atrasado desde ' if atrasado else 'Previsto para '}{pl.data_planejada.strftime('%d/%m/%Y') if pl.data_planejada else '-'}",
                            module="Treinamentos",
                            icon="bi-calendar-check",
                            url=target_url,
                            action_text="Abrir Painel",
                            date=pl.data_planejada if pl.data_planejada else hoje,
                            is_urgent=atrasado,
                            sub_type="Demanda por Instrutor"
                        )
                    )
            except Exception:
                pass
    except Exception:
        pass

    # 6. Laboratório (Ocorrências abertas)
    try:
        if has_module_access(user, "laboratorio") or user.is_superuser or user.is_staff or getattr(user, "is_authenticated", False):
            from laboratorio.models import OcorrenciaLaboratorio
            qs_lab = OcorrenciaLaboratorio.objects.filter(data_encerramento__isnull=True)[:15]
            for oc in qs_lab:
                items.append(
                    InboxItem(
                        id=f"laboratorio_{oc.id}",
                        title=f"Ocorrência Aberta: {oc.titulo or 'Laboratório'}",
                        description=f"Registrada em {oc.data_ocorrencia.strftime('%d/%m/%Y') if oc.data_ocorrencia else '-'}",
                        module="Laboratório",
                        icon="bi-flask",
                        url=reverse("laboratorio:modulo"),
                        action_text="Ver Ocorrência",
                        date=oc.data_ocorrencia if oc.data_ocorrencia else hoje,
                        is_urgent=False,
                        sub_type="Ocorrências Abertas"
                    )
                )
    except Exception:
        pass

    # 7. Quadros de Atividades (Boards)
    try:
        if has_module_access(user, "quadros") or user.is_superuser or user.is_staff or getattr(user, "is_authenticated", False):
            from boards.models import Card, BoardNotification
            from django.db.models import Q

            # 7.1 Notificações não lidas do Quadro (menções, alertas)
            try:
                if colaborador:
                    notifs_qs = BoardNotification.objects.filter(
                        colaborador=colaborador,
                        lida=False
                    ).select_related('cartao__coluna__quadro', 'criado_por')

                    for n in notifs_qs[:20]:
                        card = n.cartao
                        quadro = card.coluna.quadro if card and card.coluna else None
                        quadro_id = quadro.id if quadro else 1
                        target_url = reverse("boards:read_board_notification", args=[n.id]) if hasattr(reverse, '__call__') else f"/boards/{quadro_id}/?card={card.id}"
                        
                        items.append(
                            InboxItem(
                                id=f"board_notif_{n.id}",
                                title=f"Alerta: {card.titulo if card else 'Atividade'}",
                                description=n.mensagem or f"Atualização em {quadro.nome if quadro else 'Quadro'}",
                                module="Quadros",
                                icon="bi-chat-left-dots",
                                url=target_url,
                                action_text="Visualizar",
                                date=n.criado_em.date() if n.criado_em else hoje,
                                is_urgent=False,
                                sub_type="Menções e Alertas"
                            )
                        )
            except Exception:
                pass

            # 7.2 Tarefas Pendentes, Atrasadas e Próximas Entregas nos Quadros
            try:
                base_cards = Card.objects.filter(
                    data_conclusao__isnull=True,
                    coluna__arquivada=False,
                    coluna__quadro__arquivado=False
                ).select_related('coluna__quadro').prefetch_related('responsaveis')

                if not is_global_viewer and colaborador and not (user.is_superuser or user.is_staff):
                    scoped_cards = base_cards.filter(
                        Q(responsaveis=colaborador) | Q(criado_por=colaborador) | Q(coluna__quadro__membros=colaborador) | Q(coluna__quadro__todos_colaboradores=True)
                    ).distinct()
                    target_cards = scoped_cards
                else:
                    target_cards = base_cards

                for card in target_cards[:100]:
                    quadro = card.coluna.quadro
                    target_url = f"{reverse('boards:board_detail', args=[quadro.id])}?card={card.id}"
                    
                    if card.data_entrega:
                        if card.data_entrega < hoje:
                            dias_atraso = (hoje - card.data_entrega).days
                            items.append(
                                InboxItem(
                                    id=f"board_card_{card.id}",
                                    title=f"Ação em Atraso: {card.titulo}",
                                    description=f"Quadro: {quadro.nome} | Coluna: {card.coluna.nome} | Venceu há {dias_atraso} dias ({card.data_entrega.strftime('%d/%m/%Y')})",
                                    module="Quadros",
                                    icon="bi-kanban",
                                    url=target_url,
                                    action_text="Resolver",
                                    date=card.data_entrega,
                                    is_urgent=dias_atraso > 7 or card.prioridade == 'ALTA',
                                    sub_type="Tarefas em Atraso"
                                )
                            )
                        elif card.data_entrega <= hoje + timedelta(days=7):
                            dias_restantes = (card.data_entrega - hoje).days
                            prazo_txt = "hoje" if dias_restantes == 0 else (f"em {dias_restantes} dia(s)" if dias_restantes > 0 else "")
                            items.append(
                                InboxItem(
                                    id=f"board_card_{card.id}",
                                    title=f"Entrega Próxima: {card.titulo}",
                                    description=f"Quadro: {quadro.nome} | Coluna: {card.coluna.nome} | Vence {prazo_txt} ({card.data_entrega.strftime('%d/%m/%Y')})",
                                    module="Quadros",
                                    icon="bi-clock-history",
                                    url=target_url,
                                    action_text="Resolver",
                                    date=card.data_entrega,
                                    is_urgent=card.prioridade == 'ALTA',
                                    sub_type="Próximas Entregas"
                                )
                            )
                        else:
                            # Tarefa pendente com prazo futuro
                            items.append(
                                InboxItem(
                                    id=f"board_card_{card.id}",
                                    title=f"Tarefa: {card.titulo}",
                                    description=f"Quadro: {quadro.nome} | Coluna: {card.coluna.nome} | Prazo: {card.data_entrega.strftime('%d/%m/%Y')}",
                                    module="Quadros",
                                    icon="bi-kanban",
                                    url=target_url,
                                    action_text="Acessar",
                                    date=card.data_entrega,
                                    is_urgent=False,
                                    sub_type="Tarefas Pendentes"
                                )
                            )
                    else:
                        # Tarefa sem prazo de entrega definido
                        items.append(
                            InboxItem(
                                id=f"board_card_{card.id}",
                                title=f"Tarefa: {card.titulo}",
                                description=f"Quadro: {quadro.nome} | Coluna: {card.coluna.nome}",
                                module="Quadros",
                                icon="bi-check2-square",
                                url=target_url,
                                action_text="Acessar",
                                date=card.criado_em.date() if card.criado_em else hoje,
                                is_urgent=False,
                                sub_type="Tarefas Pendentes"
                            )
                        )
            except Exception:
                pass
    except Exception:
        pass

    # Sort items: oldest date first (most urgent)
    items.sort(key=lambda x: x.date if x.date else date.max)

    cache.set(cache_key, items, timeout=30)  # Short cache
    return items
