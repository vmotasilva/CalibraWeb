import datetime
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from .models import RegistroAuditoria, JustificativaAuditoria

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

def calcular_periodos_pendentes(modelo, limit=24):
    """
    Retorna uma lista de dicts com {'inicio': date, 'fim': date, 'label': str}
    dos períodos que não possuem Registros nem Justificativas.
    """
    hoje = timezone.localdate()
    start_date = timezone.localtime(modelo.criado_em).date()
    
    todos_periodos = iter_periodos(modelo, start_date, hoje)
    
    registros = RegistroAuditoria.objects.filter(modelo=modelo).values_list('periodo_inicio', 'periodo_fim')
    justificativas = JustificativaAuditoria.objects.filter(modelo=modelo).values_list('periodo_inicio', 'periodo_fim')
    just_set = set(justificativas)
    
    pendentes = []
    
    for p_inicio, p_fim in todos_periodos:
        # Períodos em andamento não devem constar como pendentes/vencidos.
        # Apenas períodos cujo término já passou (p_fim < hoje) são considerados pendentes.
        # Exceção para "UNICA", que permanece pendente até ser realizada.
        if modelo.periodicidade != "UNICA" and p_fim >= hoje:
            continue

        if (p_inicio, p_fim) in just_set:
            continue
            
        tem_registro = any(
            r_inicio and r_fim and (r_inicio <= p_fim and r_fim >= p_inicio)
            for r_inicio, r_fim in registros
        )
        if tem_registro:
            continue
            
        label = formatar_periodo(modelo.periodicidade, p_inicio, p_fim)
        pendentes.append({
            'inicio': p_inicio.isoformat(),
            'fim': p_fim.isoformat(),
            'label': label,
            'inicio_date': p_inicio,
            'fim_date': p_fim
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
