import datetime
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from .models import (
    RegistroAuditoria,
    JustificativaAuditoria,
    ModeloAuditoria,
    PerguntaAuditoria,
    RespostaAuditoria,
)

def iter_periodos(modelo, start_date, end_date):
    """
    Gera tuplas de (periodo_inicio, periodo_fim) de acordo com a periodicidade do modelo,
    indo de start_date até end_date.
    """
    periodos = []
    
    # Para "UNICA", não iteramos por período se já passou. Mas como é UNICA, 
    # podemos considerar que só há 1 período (da criação até hoje).
    if modelo.periodicidade == "UNICA":
        return [(start_date, end_date)]
        
    current = start_date
    
    while current <= end_date:
        if modelo.periodicidade == "DIARIA":
            p_end = current
            periodos.append((current, p_end))
            current = current + relativedelta(days=1)
            
        elif modelo.periodicidade == "SEMANAL":
            # Vamos alinhar para segunda (0) a domingo (6)
            days_to_monday = current.weekday()
            p_start = current - relativedelta(days=days_to_monday)
            p_end = p_start + relativedelta(days=6)
            if p_start not in [p[0] for p in periodos]:
                periodos.append((p_start, p_end))
            current = p_end + relativedelta(days=1)
            
        elif modelo.periodicidade == "QUINZENAL":
            # Quinzena 1: 1 a 15. Quinzena 2: 16 ao fim do mês.
            if current.day <= 15:
                p_start = current.replace(day=1)
                p_end = current.replace(day=15)
                current = p_end + relativedelta(days=1)
            else:
                p_start = current.replace(day=16)
                p_end = (current + relativedelta(months=1)).replace(day=1) - relativedelta(days=1)
                current = p_end + relativedelta(days=1)
            if p_start not in [p[0] for p in periodos]:
                periodos.append((p_start, p_end))
                
        elif modelo.periodicidade == "MENSAL":
            p_start = current.replace(day=1)
            p_end = (p_start + relativedelta(months=1)) - relativedelta(days=1)
            if p_start not in [p[0] for p in periodos]:
                periodos.append((p_start, p_end))
            current = p_end + relativedelta(days=1)
            
        elif modelo.periodicidade == "TRIMESTRAL":
            q = (current.month - 1) // 3
            p_start = current.replace(month=q * 3 + 1, day=1)
            p_end = (p_start + relativedelta(months=3)) - relativedelta(days=1)
            if p_start not in [p[0] for p in periodos]:
                periodos.append((p_start, p_end))
            current = p_end + relativedelta(days=1)
            
        elif modelo.periodicidade == "SEMESTRAL":
            s = (current.month - 1) // 6
            p_start = current.replace(month=s * 6 + 1, day=1)
            p_end = (p_start + relativedelta(months=6)) - relativedelta(days=1)
            if p_start not in [p[0] for p in periodos]:
                periodos.append((p_start, p_end))
            current = p_end + relativedelta(days=1)
            
        elif modelo.periodicidade == "ANUAL":
            p_start = current.replace(month=1, day=1)
            p_end = current.replace(month=12, day=31)
            if p_start not in [p[0] for p in periodos]:
                periodos.append((p_start, p_end))
            current = p_end + relativedelta(days=1)
            
        else:
            break
            
    return periodos

MAPA_DIA_SEMANA = {
    "SEGUNDA": 0,
    "TERCA": 1,
    "QUARTA": 2,
    "QUINTA": 3,
    "SEXTA": 4,
    "SABADO": 5,
    "DOMINGO": 6,
}

def calcular_periodos_pendentes(modelo, limit=24):
    """
    Retorna uma lista de dicts dos períodos pendentes ou em andamento.
    Campos de cada item:
    - inicio: str ISO
    - fim: str ISO
    - label: str
    - inicio_date: date
    - fim_date: date
    - status: 'EM_ANDAMENTO' | 'PENDENTE'
    - progresso: int
    - registro_id: int | None
    """
    hoje = timezone.localdate()
    start_date = timezone.localtime(modelo.criado_em).date()
    
    todos_periodos = iter_periodos(modelo, start_date, hoje)
    
    registros = list(
        RegistroAuditoria.objects.filter(modelo=modelo)
        .values('id', 'periodo_inicio', 'periodo_fim', 'status', 'progresso')
    )
    justificativas = set(
        JustificativaAuditoria.objects.filter(modelo=modelo)
        .values_list('periodo_inicio', 'periodo_fim')
    )
    
    pendentes = []
    
    for p_inicio, p_fim in todos_periodos:
        # Períodos futuros que ainda não iniciaram
        if p_inicio > hoje:
            continue

        # Registros vinculados a este período
        registros_periodo = [
            r for r in registros
            if r['periodo_inicio'] and r['periodo_fim']
            and (r['periodo_inicio'] <= p_fim and r['periodo_fim'] >= p_inicio)
        ]

        # Se houver registro concluído (100% ou status CONCLUIDO), período está finalizado
        tem_concluido = any(
            r['status'] == 'CONCLUIDO' or (r['progresso'] is not None and r['progresso'] >= 100)
            for r in registros_periodo
        )
        if tem_concluido:
            continue

        # Se houver justificativa registrada para este período
        if (p_inicio, p_fim) in justificativas:
            continue

        # Auditoria criada, mas não concluída (progresso < 100% e status != CONCLUIDO):
        reg_em_andamento = next(
            (r for r in registros_periodo if r['status'] != 'CONCLUIDO' and (r['progresso'] is None or r['progresso'] < 100)),
            None
        )

        is_periodo_atual = (p_inicio <= hoje <= p_fim)

        if reg_em_andamento:
            label = formatar_periodo(modelo.periodicidade, p_inicio, p_fim)

            # Avaliar se o dia atual está preenchido
            dia_atual_preenchido = False
            dia_hoje_nome = ""
            if is_periodo_atual and modelo.periodicidade == "SEMANAL":
                dia_keys = ["SEGUNDA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SABADO", "DOMINGO"]
                dia_hoje_key = dia_keys[hoje.weekday()]
                dia_hoje_nome = dict(ModeloAuditoria.DIA_SEMANA_CHOICES).get(dia_hoje_key, dia_hoje_key)

                perguntas_por_dia = modelo.perguntas.filter(
                    ativo=True, preenchimento_semanal="POR_DIA"
                )
                if perguntas_por_dia.exists():
                    total_esperado = perguntas_por_dia.count()
                    grid_colunas = getattr(modelo, "grid_colunas", "") or ""
                    colunas_list = [c.strip() for c in grid_colunas.split(",") if c.strip()]
                    if colunas_list:
                        total_esperado *= len(colunas_list)

                    respostas_hoje_count = RespostaAuditoria.objects.filter(
                        registro_id=reg_em_andamento["id"],
                        pergunta__in=perguntas_por_dia,
                        dia_semana=dia_hoje_key,
                    ).exclude(valor__exact="").exclude(valor__isnull=True).count()

                    dia_atual_preenchido = (respostas_hoje_count >= total_esperado and total_esperado > 0)
                else:
                    dia_atual_preenchido = (reg_em_andamento.get("progresso") or 0) >= 100
            elif is_periodo_atual:
                dia_atual_preenchido = (reg_em_andamento.get("progresso") or 0) >= 100

            pendentes.append({
                "inicio": p_inicio.isoformat(),
                "fim": p_fim.isoformat(),
                "label": label,
                "inicio_date": p_inicio,
                "fim_date": p_fim,
                "status": "EM_ANDAMENTO",
                "progresso": reg_em_andamento["progresso"] or 0,
                "registro_id": reg_em_andamento["id"],
                "dia_atual_preenchido": dia_atual_preenchido,
                "dia_atual_nome": dia_hoje_nome,
            })
            continue

        # Caso não haja auditoria criada para o período:
        if is_periodo_atual:
            if modelo.periodicidade == "SEMANAL":
                # Para auditoria semanal, a semana iniciada (ex: 31/08/2026 a 06/09/2026)
                # deve aparecer como PENDENTE desde o início da semana até se iniciar uma nova auditoria.
                pass
            elif modelo.periodicidade != "UNICA":
                # Outras periodicidades (mensal, quinzenal) só vencem após término do período
                continue
        elif p_fim >= hoje and modelo.periodicidade != "UNICA":
            continue

        label = formatar_periodo(modelo.periodicidade, p_inicio, p_fim)
        pendentes.append({
            "inicio": p_inicio.isoformat(),
            "fim": p_fim.isoformat(),
            "label": label,
            "inicio_date": p_inicio,
            "fim_date": p_fim,
            "status": "PENDENTE",
            "progresso": 0,
            "registro_id": None,
            "dia_atual_preenchido": False,
            "dia_atual_nome": "",
        })
        
    pendentes.reverse()
    if limit:
        pendentes = pendentes[:limit]
        
    return pendentes

def formatar_periodo(periodicidade, p_inicio, p_fim):
    if periodicidade == "UNICA":
        return "Aplicação Única Pendente"
    if p_inicio == p_fim:
        return p_inicio.strftime("%d/%m/%Y")
    return f"{p_inicio.strftime('%d/%m/%Y')} a {p_fim.strftime('%d/%m/%Y')}"
