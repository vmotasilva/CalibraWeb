from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
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
    sub_type: str = ""      # Sub-aba / Origem específica


def _can(user: Any, module_key: str, *view_names: str) -> bool:
    """Acesso ao módulo E a todas as seções (views) de destino do item.

    Superuser/staff passam (regra de has_module_access/has_view_access).
    """
    from shared.permissions import has_module_access, has_view_access

    if not has_module_access(user, module_key):
        return False
    return all(has_view_access(user, vn) for vn in view_names)


def invalidar_cache_inbox(user: Optional[Any] = None) -> None:
    """Invalida caches de inbox para um usuário ou todos."""
    try:
        if user:
            user_id = getattr(user, "pk", user)
            cache.delete(f"inbox_items:v9:user:{user_id}:global:False")
            cache.delete(f"inbox_items:v9:user:{user_id}:global:True")
            cache.delete(f"inbox_items:v10:user:{user_id}:global:False")
            cache.delete(f"inbox_items:v10:user:{user_id}:global:True")
            cache.delete(f"inbox_items:v11:user:{user_id}:global:False")
            cache.delete(f"inbox_items:v11:user:{user_id}:global:True")
            cache.delete(f"inbox_items:v12:user:{user_id}:global:False")
            cache.delete(f"inbox_items:v12:user:{user_id}:global:True")
        if hasattr(cache, "delete_pattern"):
            cache.delete_pattern("inbox_items:*")
    except Exception:
        pass


def get_user_inbox_items(user: Any, is_global: bool = False) -> list[InboxItem]:
    """Retorna uma lista individual de pendências reais para formar a Inbox e as Notificações por Origem."""
    if not getattr(user, "is_authenticated", False):
        return []
        
    cache_key = f"inbox_items:v12:user:{getattr(user, 'pk', 'anon')}:global:{is_global}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    items: list[InboxItem] = []
    hoje = date.today()
    is_global_viewer = is_global and _is_global_viewer(user)
    colaborador = _get_colaborador_for_user(user)
    
    from shared.permissions import has_module_access

    # =========================================================================
    # 1. AUDITORIA
    # =========================================================================
    try:
        if has_module_access(user, "auditoria"):
            from auditoria.models import ModeloAuditoria, RelatorioCompartilhadoAuditoria
            from django.db.models import Q
            from auditoria.utils_periodos import calcular_periodos_pendentes
            from urllib.parse import urlencode
            
            # 1.1 Modelos com períodos em atraso
            modelos = ModeloAuditoria.objects.filter(ativo=True)
            if not is_global_viewer:
                scoped_modelos = modelos.filter(Q(responsavel=user) | Q(responsaveis=user)).distinct()
                target_modelos = scoped_modelos if scoped_modelos.exists() else (modelos if user.is_superuser or user.is_staff else scoped_modelos)
            else:
                target_modelos = modelos
                
            for modelo in target_modelos:
                periodos = calcular_periodos_pendentes(modelo, limit=3)
                for p in periodos:
                    fim_date = p.get('fim_date')
                    if fim_date:
                        is_em_andamento = (p.get('status') == 'EM_ANDAMENTO')
                        dia_atual_preenchido = p.get('dia_atual_preenchido', False)

                        # Se estiver em andamento e o dia atual já estiver preenchido,
                        # não cobra nas notificações de hoje
                        if is_em_andamento and dia_atual_preenchido:
                            continue

                        action_text = "Continuar" if is_em_andamento else "Preencher"
                        # Em andamento com período já encerrado = atrasada
                        # Seção de destino: editar registro (em andamento) ou iniciar nova auditoria
                        if not _can(user, "auditoria", "auditoria:registro_edit" if is_em_andamento and p.get('registro_id') else "auditoria:selecionar_modelo_preenchimento"):
                            continue
                        is_atrasada = is_em_andamento and bool(p.get('atrasado'))
                        if is_atrasada:
                            title = f"Auditoria Atrasada: {modelo.nome}"
                        else:
                            title = f"Auditoria em Andamento: {modelo.nome}" if is_em_andamento else f"Preencher Auditoria: {modelo.nome}"
                        sub_type = "Auditorias em Andamento" if is_em_andamento and not is_atrasada else "Períodos em Atraso"
                        url = reverse("auditoria:registro_edit", args=[p['registro_id']]) if is_em_andamento and p.get('registro_id') else reverse("auditoria:selecionar_modelo_preenchimento")
                        
                        if is_atrasada:
                            desc = f"Prazo encerrado, ainda em andamento ({p.get('progresso', 0)}%): {p['label']}"
                        elif is_em_andamento:
                            dia_nome = p.get('dia_atual_nome')
                            if dia_nome:
                                desc = f"Preenchimento de hoje ({dia_nome}) pendente &bull; {p['label']} ({p.get('progresso', 0)}%)"
                            else:
                                desc = f"Em andamento ({p.get('progresso', 0)}%): {p['label']}"
                        else:
                            desc = f"Período pendente: {p['label']}"

                        item_id = f"auditoria_{modelo.id}_{fim_date.isoformat()}_{p.get('registro_id') or 'novo'}"
                        items.append(
                            InboxItem(
                                id=item_id,
                                title=title,
                                description=desc,
                                module="Auditoria",
                                icon="bi-exclamation-triangle-fill" if is_atrasada else ("bi-clock-history" if is_em_andamento else "bi-clipboard-check"),
                                url=url,
                                action_text=action_text,
                                date=fim_date,
                                is_urgent=is_atrasada or ((hoje - fim_date).days > 30 and not is_em_andamento),
                                sub_type=sub_type
                            )
                        )
            
            # 1.2 Relatórios Compartilhados Pendentes de Leitura
            now = timezone.now()
            shares_qs = RelatorioCompartilhadoAuditoria.objects.filter(
                destinatario=user, ativo=True, recebido_em__isnull=True
            ).filter(Q(expira_em__isnull=True) | Q(expira_em__gt=now)).select_related("remetente", "modelo")
            if not _can(user, "auditoria", "auditoria:registros_por_modelo_compartilhado"):
                shares_qs = shares_qs.none()
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

    # 1.3 Ocorrências de auditoria atribuídas ao colaborador (responsável pela tratativa)
    try:
        from auditoria.models import ComentarioRespostaAuditoria

        atribuidas = (
            ComentarioRespostaAuditoria.objects.filter(
                responsaveis__user_django=user,
                requer_tratativa=True,
                status=ComentarioRespostaAuditoria.STATUS_ABERTA,
                unificada_em__isnull=True,
            )
            .select_related("pergunta", "pergunta__modelo")
            .distinct()
            .order_by("prazo", "-criado_em")[:50]
        )
        for oc in atribuidas:
            vencida = bool(oc.prazo and oc.prazo < hoje)
            prazo_txt = f" · prazo {oc.prazo:%d/%m/%Y}" if oc.prazo else ""
            texto = (oc.acao or oc.texto or "").strip()
            items.append(
                InboxItem(
                    id=f"auditoria_ocorrencia_{oc.id}",
                    title=f"Ocorrência atribuída a você: {oc.pergunta.modelo.nome}",
                    description=f"{texto[:140]}{prazo_txt}",
                    module="Auditoria",
                    icon="bi-exclamation-diamond",
                    url=reverse("auditoria:modulo") + "#ocorrencias-em-aberto",
                    action_text="Tratar",
                    date=oc.prazo or oc.criado_em.date(),
                    is_urgent=vencida,
                    sub_type="Ocorrências Atribuídas",
                )
            )
    except Exception:
        pass

    # =========================================================================
    # 2. METROLOGIA - CALIBRAÇÕES VENCIDAS
    # =========================================================================
    try:
        if _can(user, "metrologia", "modulo_metrologia"):
            from metrologia.models import Instrumento
            from django.db.models import Q

            global_vencidos = Instrumento.objects.filter(
                ativo=True,
                data_proxima_calibracao__lt=hoje,
            ).select_related('responsavel')
            
            if not is_global_viewer:
                # Sem colaborador vinculado: só instrumentos sem responsável
                target_vencidos = global_vencidos.filter(
                    Q(responsavel=colaborador) | Q(responsavel__isnull=True)
                    if colaborador else Q(responsavel__isnull=True)
                )
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

    # =========================================================================
    # 3. METROLOGIA - COTAÇÕES EM ATRASO
    # =========================================================================
    try:
        if _can(user, "metrologia", "metrologia:solicitacao_list"):
            from metrologia.models import SolicitacaoCotacao

            global_cotacoes = SolicitacaoCotacao.objects.filter(
                status="SOLICITADO",
                data_necessidade__lt=hoje,
            ).select_related('responsavel')
            
            if not is_global_viewer:
                target_cotacoes = global_cotacoes.filter(responsavel=colaborador) if colaborador else global_cotacoes.none()
            else:
                target_cotacoes = global_cotacoes

            for sc in target_cotacoes[:50]:
                dias_atraso = (hoje - sc.data_necessidade).days if sc.data_necessidade else 0
                items.append(
                    InboxItem(
                        id=f"cotacao_{sc.id}",
                        title=f"Cotação Atrasada: #{sc.id} ({sc.tipo_servico})",
                        description=f"Necessidade era {sc.data_necessidade.strftime('%d/%m/%Y')} ({dias_atraso} dias de atraso)",
                        module="Metrologia",
                        icon="bi-cash-coin",
                        url=reverse("metrologia:solicitacoes_cotacao"),
                        action_text="Resolver",
                        date=sc.data_necessidade,
                        is_urgent=dias_atraso > 7,
                        sub_type="Cotações em Atraso"
                    )
                )
    except Exception:
        pass

    # =========================================================================
    # 4. METROLOGIA - OCORRÊNCIAS EM ABERTO & TRATATIVAS
    # =========================================================================
    try:
        from qms.models import OcorrenciaInstrumento
        from django.db.models import Q

        # Só quem acessa o módulo e o Relatório de Ocorrências (destino do item)
        if _can(user, "metrologia", "metrologia:relatorio_ocorrencias"):
            ocorrencias_abertas = OcorrenciaInstrumento.objects.filter(
                status="ABERTA"
            ).select_related("instrumento", "instrumento__setor", "usuario_responsavel").order_by("-data_ocorrencia")
        else:
            ocorrencias_abertas = OcorrenciaInstrumento.objects.none()

        for oc in ocorrencias_abertas[:50]:
            inst = oc.instrumento
            inst_tag = (inst.tag or inst.codigo or f"ID {inst.id}") if inst else "Instrumento"
            inst_desc = f"{inst.descricao} — " if inst and inst.descricao else ""
            setor_nome = f" ({inst.setor.nome})" if inst and inst.setor else ""
            tipo_nome = oc.get_tipo_display() if hasattr(oc, 'get_tipo_display') else oc.tipo
            
            uid_atual = getattr(user, 'id', None)
            is_minha_tratativa = (
                oc.usuario_responsavel_id == uid_atual
                or oc.mensagens.filter(destinatarios__id=uid_atual).exists()
            )
            
            if is_minha_tratativa:
                sub_tipo_name = "Minhas Tratativas"
                titulo_item = f"Tratativa de Ocorrência ({tipo_nome}): {inst_tag}{setor_nome}"
                acao_texto = "Tratar"
            else:
                sub_tipo_name = "Ocorrências em Aberto"
                titulo_item = f"Ocorrência Aberta ({tipo_nome}): {inst_tag}{setor_nome}"
                acao_texto = "Visualizar"
            
            try:
                target_url = reverse("metrologia:relatorio_ocorrencias") + f"?ocorrencia_id={oc.id}"
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
                    title=titulo_item,
                    description=f"{inst_desc}{oc.descricao}",
                    module="Metrologia",
                    icon="bi-exclamation-octagon",
                    url=target_url,
                    action_text=acao_texto,
                    date=data_oc,
                    is_urgent=True,
                    sub_type=sub_tipo_name
                )
            )
    except Exception:
        pass

    # =========================================================================
    # 4.1 PLANO DE AÇÃO DE OCORRÊNCIAS (ações atribuídas ao usuário, de qualquer módulo)
    # =========================================================================
    try:
        from shared.models import AcaoOcorrencia

        nomes_origem = {"auditoria": "Auditoria", "laboratorio": "Laboratório", "pcp": "PCP",
                        "metrologia": "Metrologia", "kpi": "KPI"}
        for a in AcaoOcorrencia.objects.filter(responsavel=user, status="ABERTA").order_by("prazo", "criado_em")[:50]:
            vencida = bool(a.prazo and a.prazo < hoje)
            prazo_txt = f" · prazo {a.prazo:%d/%m/%Y}" if a.prazo else ""
            items.append(
                InboxItem(
                    id=f"acao_ocorrencia_{a.id}",
                    title=f"Ação de ocorrência atribuída a você ({nomes_origem.get(a.origem, a.origem)})",
                    description=f"{a.descricao[:140]}{prazo_txt}",
                    module="Ocorrências",
                    icon="bi-exclamation-triangle",
                    url=reverse("ocorrencias_central") + f"?aba=minhas&origem={a.origem}",
                    action_text="Tratar",
                    date=a.prazo or a.criado_em.date(),
                    is_urgent=vencida,
                    sub_type="Minhas ações",
                )
            )
    except Exception:
        pass

    # =========================================================================
    # 5. TREINAMENTOS (Eficácia, Demandas por Liderança e Instrutor)
    # =========================================================================
    try:
        if has_module_access(user, "procedures"):
            can_eficacia = _can(user, "procedures", "procedures:avaliacao_eficacia_list")
            can_dash_trein = _can(user, "procedures", "procedures:dashboard_treinamentos")
            can_matriz_val = _can(user, "procedures", "procedures:matriz_avaliacoes")
            can_planej = _can(user, "procedures", "procedures:detalhe_planejamento")
            from procedures.models import (
                RegistroTreinamento,
                SolicitacaoValidacaoMatriz,
                PlanejamentoTreinamento,
                ResponsavelTreinamentoMatriz,
                ColaboradorPerfil,
            )
            from datetime import timedelta
            from django.db.models import (
                Q,
                F,
                Subquery,
                OuterRef,
                Case,
                When,
                Value,
                IntegerField,
                Exists,
            )

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

            if not can_eficacia or (not is_global_viewer and not colaborador):
                qs_eficacia = qs_eficacia.none()
            if not is_global_viewer and colaborador:
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
                target_eficacia = scoped_eficacia
            else:
                target_eficacia = qs_eficacia

            from urllib.parse import urlencode

            for t in target_eficacia[:20]:
                dias = (hoje - t.data_treinamento).days
                
                # Montar parâmetros da URL com filtros específicos
                params = {
                    "procedimento": str(t.procedimento_id),
                    "status": "PENDENTE",
                }
                
                # Gestor / Responsável: prioriza o usuário logado (colaborador), ou gestor responsável direcionado
                if colaborador:
                    params["gestor"] = str(colaborador.id)
                elif t.gestor_responsavel_id:
                    params["gestor"] = str(t.gestor_responsavel_id)
                elif t.colaborador.lider_id:
                    params["gestor"] = str(t.colaborador.lider_id)
                elif t.colaborador.supervisor_id:
                    params["gestor"] = str(t.colaborador.supervisor_id)
                elif t.colaborador.gerente_id:
                    params["gestor"] = str(t.colaborador.gerente_id)

                url_avaliacao = f"{reverse('procedures:avaliacao_eficacia_list')}?{urlencode(params)}"

                items.append(
                    InboxItem(
                        id=f"eficacia_{t.id}",
                        title=f"Avaliação de Eficácia: {t.colaborador.nome_completo}",
                        description=f"Treinamento crítico {t.procedimento.codigo} realizado há {dias} dias",
                        module="Treinamentos",
                        icon="bi-mortarboard",
                        url=url_avaliacao,
                        action_text="Avaliar",
                        date=t.data_treinamento,
                        is_urgent=dias > 60,
                        sub_type="Avaliação de Eficácia"
                    )
                )

            # Subquery para pegar apenas o registro mais recente por colaborador + procedimento
            latest_id_subquery = RegistroTreinamento.objects.filter(
                colaborador_id=OuterRef('colaborador_id'),
                procedimento_id=OuterRef('procedimento_id'),
                ativo=True
            ).annotate(
                has_valid_date=Case(
                    When(data_treinamento__isnull=False, data_treinamento__gt=date(1970, 1, 1), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-has_valid_date', '-data_treinamento', '-id').values('id')[:1]

            # Garantir que o procedimento faz parte de um perfil ativo do colaborador
            perfil_exists_qs = ColaboradorPerfil.objects.filter(
                colaborador_id=OuterRef('colaborador_id'),
                ativo=True,
                perfil__grupos__subgrupos__procedimentos=OuterRef('procedimento_id'),
            )

            # Definição unificada de status pendente de treinamento
            pendencias_demanda = (
                Q(data_treinamento__isnull=True)
                | Q(data_treinamento__lte=date(1970, 1, 1))
                | (
                    Q(procedimento__data_aprovacao__isnull=False)
                    & Q(data_treinamento__lt=F("procedimento__data_aprovacao"))
                )
            )

            # Base de demandas verdadeiramente pendentes
            qs_base_pendentes = RegistroTreinamento.objects.filter(
                ativo=True,
                tipo="PROCEDIMENTO",
                procedimento__isnull=False,
                colaborador__is_active=True,
                colaborador__afastado=False,
                colaborador__em_ferias=False,
                id=Subquery(latest_id_subquery)
            ).annotate(
                _in_perfil=Exists(perfil_exists_qs)
            ).filter(
                _in_perfil=True
            ).filter(
                pendencias_demanda
            ).select_related("colaborador", "procedimento")

            # 5.2 Demandas de Treinamento Pendentes por Liderança (Agrupadas por Colaborador)
            if not can_dash_trein or (not is_global_viewer and not colaborador):
                qs_base_pendentes = qs_base_pendentes.none()
            if not is_global_viewer and colaborador:
                scoped_demandas = qs_base_pendentes.filter(
                    Q(colaborador=colaborador) | Q(colaborador__lider=colaborador) | Q(colaborador__supervisor=colaborador) | Q(colaborador__gerente=colaborador)
                )
                target_demandas = scoped_demandas
            else:
                target_demandas = qs_base_pendentes

            # Agrupar demandas de liderança por colaborador
            demandas_lider_por_colab = {}
            for d in target_demandas[:100]:
                cid = d.colaborador_id
                if cid not in demandas_lider_por_colab:
                    lider_id = str(d.colaborador.lider_id) if d.colaborador and d.colaborador.lider_id else (str(colaborador.id) if colaborador else "")
                    demandas_lider_por_colab[cid] = {
                        'colaborador': d.colaborador,
                        'procedimentos': [],
                        'lider_id': lider_id,
                        'data': d.criado_em.date() if hasattr(d, "criado_em") and d.criado_em else hoje,
                    }
                if d.procedimento.codigo not in demandas_lider_por_colab[cid]['procedimentos']:
                    demandas_lider_por_colab[cid]['procedimentos'].append(d.procedimento.codigo)

            for cid, data_lid in list(demandas_lider_por_colab.items())[:20]:
                colab = data_lid['colaborador']
                procs = data_lid['procedimentos']
                total_p = len(procs)
                if total_p == 1:
                    desc = f"Procedimento {procs[0]} pendente de treinamento da equipe"
                else:
                    procs_str = ", ".join(procs[:3]) + (f" e mais {total_p - 3}" if total_p > 3 else "")
                    desc = f"{total_p} procedimentos pendentes: {procs_str}"

                target_url = f"{reverse('procedures:dashboard_treinamentos')}?colaborador_id={colab.id}&status_treinamento=PENDENTE"
                if data_lid['lider_id']:
                    target_url += f"&lider={data_lid['lider_id']}"

                items.append(
                    InboxItem(
                        id=f"demanda_lider_{colab.id}",
                        title=f"Demanda Liderança: {colab.nome_completo}",
                        description=desc,
                        module="Treinamentos",
                        icon="bi-book",
                        url=target_url,
                        action_text="Abrir Painel",
                        date=data_lid['data'],
                        is_urgent=False,
                        sub_type="Demanda por Liderança"
                    )
                )

            # 5.3 Validações de Matriz de Habilidade
            try:
                qs_matriz = SolicitacaoValidacaoMatriz.objects.filter(
                    status="pendente",
                ).select_related("colaborador")
                if not can_matriz_val or (not is_global_viewer and not colaborador):
                    qs_matriz = qs_matriz.none()
                if not is_global_viewer and colaborador:
                    scoped_matriz = qs_matriz.filter(validador=colaborador)
                    target_matriz = scoped_matriz
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

            # 5.4 Demanda por Instrutor (Agrupadas por Colaborador)
            try:
                # A. Instrutores Responsáveis por Matriz / Sub-Área
                qs_resp_matriz = ResponsavelTreinamentoMatriz.objects.select_related(
                    "matriz", "sub_area", "colaborador"
                )
                if not can_dash_trein or (not is_global_viewer and not colaborador):
                    qs_resp_matriz = qs_resp_matriz.none()
                elif not is_global_viewer:
                    qs_resp_matriz = qs_resp_matriz.filter(colaborador=colaborador)

                # Dicionário para agrupar todas as pendências por colaborador
                pendencias_por_colab = {}

                for rm in qs_resp_matriz:
                    matriz_nome = rm.matriz.nome if rm.matriz else ""
                    sub_nome = rm.sub_area.nome if rm.sub_area else ""
                    instrutor_id = str(rm.colaborador_id)
                    scope_label = matriz_nome + (f" - {sub_nome}" if sub_nome else "")

                    demanda_escopo_qs = qs_base_pendentes.filter(procedimento__instrutor_fixo__isnull=True)

                    if matriz_nome:
                        demanda_escopo_qs = demanda_escopo_qs.filter(procedimento__matriz__iexact=matriz_nome)
                    if sub_nome:
                        demanda_escopo_qs = demanda_escopo_qs.filter(procedimento__sub_area__iexact=sub_nome)
                    if rm.turno:
                        demanda_escopo_qs = demanda_escopo_qs.filter(colaborador__turno=rm.turno)

                    for d in demanda_escopo_qs[:50]:
                        cid = d.colaborador_id
                        if cid not in pendencias_por_colab:
                            pendencias_por_colab[cid] = {
                                'colaborador': d.colaborador,
                                'procedimentos': [],
                                'scopes': set(),
                                'turno': d.colaborador.turno or rm.turno or 'Geral',
                                'instrutor_id': instrutor_id,
                                'data': d.criado_em.date() if hasattr(d, "criado_em") and d.criado_em else (rm.atualizado_em.date() if rm.atualizado_em else hoje),
                            }
                        if d.procedimento.codigo not in pendencias_por_colab[cid]['procedimentos']:
                            pendencias_por_colab[cid]['procedimentos'].append(d.procedimento.codigo)
                        if scope_label:
                            pendencias_por_colab[cid]['scopes'].add(scope_label)

                # B. Procedimentos com Instrutor Fixo
                qs_procs_fixos = qs_base_pendentes.filter(procedimento__instrutor_fixo__isnull=False).select_related('procedimento__instrutor_fixo')
                if not can_dash_trein or (not is_global_viewer and not colaborador):
                    qs_procs_fixos = qs_procs_fixos.none()
                elif not is_global_viewer:
                    qs_procs_fixos = qs_procs_fixos.filter(procedimento__instrutor_fixo=colaborador)

                for d in qs_procs_fixos[:50]:
                    cid = d.colaborador_id
                    instrutor_fixo = d.procedimento.instrutor_fixo
                    if not instrutor_fixo:
                        continue
                    instrutor_id = str(instrutor_fixo.id)
                    scope_label = f"Instrutor Fixo ({d.procedimento.codigo})"
                    if cid not in pendencias_por_colab:
                        pendencias_por_colab[cid] = {
                            'colaborador': d.colaborador,
                            'procedimentos': [],
                            'scopes': set(),
                            'turno': d.colaborador.turno or 'Geral',
                            'instrutor_id': instrutor_id,
                            'data': d.criado_em.date() if hasattr(d, "criado_em") and d.criado_em else hoje,
                        }
                    if d.procedimento.codigo not in pendencias_por_colab[cid]['procedimentos']:
                        pendencias_por_colab[cid]['procedimentos'].append(d.procedimento.codigo)
                    pendencias_por_colab[cid]['scopes'].add(scope_label)

                # Gerar 1 card único por colaborador para as responsabilidades de matriz
                for cid, pdata in list(pendencias_por_colab.items())[:30]:
                    colab = pdata['colaborador']
                    procs = pdata['procedimentos']
                    scopes_str = ", ".join(pdata['scopes']) if pdata['scopes'] else "Treinamentos"
                    total_p = len(procs)

                    if total_p == 1:
                        desc = f"Procedimento {procs[0]} ({scopes_str}) - Turno {pdata['turno']}"
                    else:
                        procs_summary = ", ".join(procs[:3])
                        if total_p > 3:
                            procs_summary += f" e mais {total_p - 3}"
                        desc = f"{total_p} procedimentos pendentes: {procs_summary} ({scopes_str}) - Turno {pdata['turno']}"

                    target_url = f"{reverse('procedures:dashboard_treinamentos')}?colaborador_id={colab.id}&instrutor_responsavel={pdata['instrutor_id']}&status_treinamento=PENDENTE"

                    items.append(
                        InboxItem(
                            id=f"demanda_instrutor_colab_{colab.id}",
                            title=f"Demanda Instrutor: {colab.nome_completo}",
                            description=desc,
                            module="Treinamentos",
                            icon="bi-person-video3",
                            url=target_url,
                            action_text="Abrir Painel",
                            date=pdata['data'],
                            is_urgent=False,
                            sub_type="Demanda por Instrutor"
                        )
                    )
            except Exception:
                pass

            # 5.5 Treinamentos Planejados (Em Andamento / Confirmados / Atrasados)
            try:
                # Atualizar status dos planejamentos vencidos para ATRASADO apenas se não estiver cancelado ou realizado
                PlanejamentoTreinamento.objects.exclude(
                    Q(status__iexact="REALIZADO") | Q(status__iexact="CANCELADO") | Q(status__iexact="ATRASADO")
                ).filter(
                    data_prevista__lt=hoje
                ).update(status="ATRASADO")

                # "Precisamos de uma notificação para treinamentos planejados e que estão em andamento ou atrasados.
                # Eles saem da notificação se estiverem cancelados ou concluídos.
                # Tanto o instrutor quanto os líderes devem receber essa notificação."
                qs_plan = PlanejamentoTreinamento.objects.exclude(
                    Q(status__iexact="REALIZADO") | Q(status__iexact="CANCELADO")
                ).select_related("instrutor").prefetch_related("colaboradores", "procedimentos")

                if not can_planej or (not is_global_viewer and not colaborador):
                    qs_plan = qs_plan.none()
                elif not is_global_viewer:
                    qs_plan = qs_plan.filter(
                        Q(instrutor=colaborador)
                        | Q(colaboradores__lider=colaborador)
                        | Q(colaboradores__supervisor=colaborador)
                        | Q(colaboradores__gerente=colaborador)
                    ).distinct()

                for pl in qs_plan[:40]:
                    atrasado = bool(pl.status == "ATRASADO" or (pl.data_prevista and pl.data_prevista < hoje))
                    status_label = "Atrasado" if atrasado else ("Confirmado" if pl.status == "CONFIRMADO" else "Planejado")

                    procs = [p.codigo for p in pl.procedimentos.all()]
                    procs_str = f" • Proc: {', '.join(procs[:2])}" if procs else ""
                    total_parts = pl.colaboradores.count()
                    instrutor_nome = pl.instrutor.nome_completo if pl.instrutor else "Instrutor a definir"

                    if atrasado:
                        title = f"Treinamento Atrasado: {pl.titulo}"
                        desc = f"Atrasado desde {pl.data_prevista.strftime('%d/%m/%Y')} • Instrutor: {instrutor_nome} • {total_parts} participante(s){procs_str}"
                    else:
                        title = f"Treinamento Planejado: {pl.titulo}"
                        desc = f"Previsto para {pl.data_prevista.strftime('%d/%m/%Y')} ({status_label}) • Instrutor: {instrutor_nome} • {total_parts} participante(s){procs_str}"

                    target_url = reverse("procedures:detalhe_planejamento", args=[pl.id])

                    items.append(
                        InboxItem(
                            id=f"planejamento_treinamento_{pl.id}",
                            title=title,
                            description=desc,
                            module="Treinamentos",
                            icon="bi-calendar-x" if atrasado else "bi-calendar-event",
                            url=target_url,
                            action_text="Ver Planejamento",
                            date=pl.data_prevista if pl.data_prevista else hoje,
                            is_urgent=atrasado,
                            sub_type="Treinamentos Planejados"
                        )
                    )
            except Exception:
                pass
    except Exception:
        pass

    # =========================================================================
    # 6. LABORATÓRIO (Ocorrências em aberto)
    # =========================================================================
    try:
        if _can(user, "laboratorio", "laboratorio:modulo"):
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

    # =========================================================================
    # 7. QUADROS DE ATIVIDADES (BOARDS)
    # =========================================================================
    try:
        if _can(user, "boards", "boards:board_detail"):
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

                if not is_global_viewer:
                    target_cards = base_cards.filter(
                        Q(responsaveis=colaborador) | Q(criado_por=colaborador) | Q(coluna__quadro__membros=colaborador) | Q(coluna__quadro__todos_colaboradores=True)
                    ).distinct() if colaborador else base_cards.none()
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

    # =========================================================================
    # 8. DIAGRAMAS (DOC.071): aprovações pendentes e revisões devolvidas
    # =========================================================================
    try:
        from django.conf import settings as dj_settings
        from procedures.models_diagram import DiagramaVersao, StatusDiagrama
        from shared.permissions import _user_has_nav_perm

        def _data_ref(dt):
            return timezone.localtime(dt).date() if dt else hoje

        tem_modulo_diagramas = has_module_access(user, "diagramas")

        # 8.1 Para aprovadores: revisões aguardando aprovação (exceto as que o próprio usuário submeteu, se há segregação)
        if tem_modulo_diagramas and (user.is_superuser or _user_has_nav_perm(user, "core.nav_diagramas_aprovar")):
            pendentes = DiagramaVersao.objects.filter(status=StatusDiagrama.EM_APROVACAO).select_related("diagrama", "submetido_por")
            if getattr(dj_settings, "DIAGRAMAS_EXIGIR_SEGREGACAO_FUNCOES", True):
                pendentes = pendentes.exclude(submetido_por=user)
            for v in pendentes:
                quem = (v.submetido_por.get_full_name() or v.submetido_por.username) if v.submetido_por else "—"
                dias = (hoje - _data_ref(v.data_submissao)).days
                items.append(
                    InboxItem(
                        id=f"diagrama_aprovar_{v.id}",
                        title=f"Aprovar diagrama {v.diagrama.identificador} - {v.diagrama.titulo}",
                        description=f"Rev. {v.revisao:02d} submetida por {quem}",
                        module="Diagramas",
                        icon="bi-diagram-3",
                        url=reverse("procedures:diagrama_editor", kwargs={"versao_id": v.id}),
                        action_text="Revisar",
                        date=_data_ref(v.data_submissao),
                        is_urgent=dias >= 5,
                        sub_type="Aguardando aprovação",
                    )
                )

        # 8.2 Para elaboradores: revisões devolvidas pelo aprovador (rascunho com motivo de devolução)
        devolvidas = DiagramaVersao.objects.filter(
            status=StatusDiagrama.RASCUNHO, motivo_devolucao__isnull=False
        ).exclude(motivo_devolucao="").filter(
            Q(submetido_por=user) | Q(diagrama__criado_por=user)
        ).select_related("diagrama").distinct()
        if not tem_modulo_diagramas:
            devolvidas = devolvidas.none()
        for v in devolvidas:
            items.append(
                InboxItem(
                    id=f"diagrama_devolvido_{v.id}",
                    title=f"Diagrama devolvido {v.diagrama.identificador} - {v.diagrama.titulo}",
                    description=f"Rev. {v.revisao:02d}: {v.motivo_devolucao[:120]}",
                    module="Diagramas",
                    icon="bi-arrow-return-left",
                    url=reverse("procedures:diagrama_editor", kwargs={"versao_id": v.id}),
                    action_text="Ajustar",
                    date=_data_ref(v.atualizado_em),
                    is_urgent=True,
                    sub_type="Devolvidos para ajuste",
                )
            )
    except Exception:
        pass

    # Sort items: oldest date first (most urgent)
    items.sort(key=lambda x: x.date if x.date else date.max)

    cache.set(cache_key, items, timeout=30)  # Short cache
    return items
