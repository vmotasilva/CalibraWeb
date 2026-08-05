# 🔧 Guia Administrativo - Sistema de Validação

## 📋 Índice
1. [Comandos Django](#comandos-django)
2. [Configuração do Admin](#configuração-do-admin)
3. [Queries SQL](#queries-sql)
4. [Limpeza e Manutenção](#limpeza-e-manutenção)
5. [Troubleshooting](#troubleshooting)

---

## 🎯 Comandos Django

### **1. Criar/Aplicar Migrations**
```bash
# Criar migrations dos modelos
python manage.py makemigrations procedures

# Ver o que será alterado
python manage.py sqlmigrate procedures 0017

# Aplicar migrations
python manage.py migrate procedures
```

### **2. Ver Status do Banco**
```bash
# Mostrar todas as migrations aplicadas
python manage.py showmigrations procedures

# Ver histórico de migrações
python manage.py showmigrations --plan procedures
```

### **3. Testar o Sistema**
```bash
# Executar script de teste completo
python test_validacao_sistema.py

# Resultado esperado:
# ======================================================================
# TESTE DO SISTEMA DE VALIDAÇÃO DE MATRIZ
# ======================================================================
# 
# 1️⃣  Buscando dados de teste...
# ✅ Matriz: [Nome da Matriz]
# ...
# ✅ TODOS OS TESTES PASSARAM!
```

### **4. Shell Interativo do Django**
```bash
# Entrar no shell
python manage.py shell

# Dentro do shell:
from procedures.models import SolicitacaoValidacaoMatriz, HistoricoValidacaoMassa
from procedures.models import MatrizHabilidade

# Ver todas as solicitações
SolicitacaoValidacaoMatriz.objects.all()

# Ver solicitações pendentes
SolicitacaoValidacaoMatriz.objects.filter(status='pendente')

# Ver histórico de validações
HistoricoValidacaoMassa.objects.all()

# Contar registros
SolicitacaoValidacaoMatriz.objects.count()

# Sair
exit()
```

---

## 🛡️ Configuração do Admin

### **1. Registrar Modelos (models.py)**
```python
from django.contrib import admin
from .models import SolicitacaoValidacaoMatriz, HistoricoValidacaoMassa

@admin.register(SolicitacaoValidacaoMatriz)
class SolicitacaoValidacaoMatrizAdmin(admin.ModelAdmin):
    list_display = ('matriz', 'solicitante', 'validador', 'status', 'criado_em')
    list_filter = ('status', 'criado_em')
    search_fields = ('matriz__nome', 'solicitante__nome_completo')
    readonly_fields = ('criado_em', 'validado_em')
    ordering = ('-criado_em',)

@admin.register(HistoricoValidacaoMassa)
class HistoricoValidacaoMassaAdmin(admin.ModelAdmin):
    list_display = ('matriz', 'validador', 'total_avaliacoes', 'executado_em')
    list_filter = ('executado_em',)
    search_fields = ('matriz__nome', 'validador__nome_completo')
    readonly_fields = ('executado_em',)
    ordering = ('-executado_em',)
```

### **2. Acessar Admin**
```
http://localhost:8000/admin/
Login com superusuário
Procedures → Solicitacao validacao matrizes
Procedures → Historico validacao massas
```

---

## 💾 Queries SQL

### **1. Ver Solicitações Pendentes**
```sql
SELECT 
    s.id,
    m.nome as matriz,
    c1.nome_completo as solicitante,
    c2.nome_completo as validador,
    s.status,
    s.criado_em
FROM procedures_solicitacaovalidacaomatriz s
JOIN procedures_matrizhabilidade m ON s.matriz_id = m.id
LEFT JOIN rh_colaborador c1 ON s.solicitante_id = c1.id
JOIN rh_colaborador c2 ON s.validador_id = c2.id
WHERE s.status = 'pendente'
ORDER BY s.criado_em DESC;
```

### **2. Histórico de Validações de um Validador**
```sql
SELECT 
    h.id,
    m.nome as matriz,
    c.nome_completo as validador,
    h.total_avaliacoes,
    h.avaliacoes_atualizadas,
    h.executado_em,
    h.motivo
FROM procedures_historicovalidacaomassa h
JOIN procedures_matrizhabilidade m ON h.matriz_id = m.id
JOIN rh_colaborador c ON h.validador_id = c.id
WHERE c.id = [ID_DO_VALIDADOR]
ORDER BY h.executado_em DESC;
```

### **3. Estatísticas de Validação**
```sql
-- Total de solicitações por status
SELECT 
    status,
    COUNT(*) as total
FROM procedures_solicitacaovalidacaomatriz
GROUP BY status;

-- Validador mais ativo
SELECT 
    c.nome_completo,
    COUNT(*) as validacoes
FROM procedures_historicovalidacaomassa h
JOIN rh_colaborador c ON h.validador_id = c.id
GROUP BY c.id, c.nome_completo
ORDER BY validacoes DESC;

-- Matrizes mais validadas
SELECT 
    m.nome,
    COUNT(*) as validacoes
FROM procedures_historicovalidacaomassa h
JOIN procedures_matrizhabilidade m ON h.matriz_id = m.id
GROUP BY m.id, m.nome
ORDER BY validacoes DESC;
```

### **4. Deletar Registros Antigos**
```bash
# CUIDADO: Isto deleta dados permanentemente!

# Via shell Django
python manage.py shell

from procedures.models import SolicitacaoValidacaoMatriz, HistoricoValidacaoMassa
from datetime import datetime, timedelta

# Deletar solicitações com mais de 1 ano
old_date = datetime.now() - timedelta(days=365)
SolicitacaoValidacaoMatriz.objects.filter(criado_em__lt=old_date).delete()

# Backup first!
```

---

## 🧹 Limpeza e Manutenção

### **1. Backup de Dados**
```bash
# Exportar dados para fixture
python manage.py dumpdata procedures.SolicitacaoValidacaoMatriz > solicitacoes_backup.json
python manage.py dumpdata procedures.HistoricoValidacaoMassa > historicos_backup.json

# Restaurar dados
python manage.py loaddata solicitacoes_backup.json
python manage.py loaddata historicos_backup.json
```

### **2. Limpar Solicitações Rejeitadas Antigo**
```bash
python manage.py shell

from procedures.models import SolicitacaoValidacaoMatriz
from datetime import datetime, timedelta

# Deletar rejeitadas com mais de 6 meses
old_date = datetime.now() - timedelta(days=180)
count = SolicitacaoValidacaoMatriz.objects.filter(
    status='rejeitada',
    validado_em__lt=old_date
).delete()[0]

print(f"Deletados {count} registros antigos")
```

### **3. Estatísticas do Sistema**
```bash
python manage.py shell

from procedures.models import SolicitacaoValidacaoMatriz, HistoricoValidacaoMassa

# Total de solicitações
total_sol = SolicitacaoValidacaoMatriz.objects.count()

# Pendentes
pendentes = SolicitacaoValidacaoMatriz.objects.filter(status='pendente').count()

# Validadas
validadas = SolicitacaoValidacaoMatriz.objects.filter(status='validada').count()

# Histórico total
total_hist = HistoricoValidacaoMassa.objects.count()

print(f"""
ESTATÍSTICAS DO SISTEMA:
- Total de Solicitações: {total_sol}
- Pendentes: {pendentes}
- Validadas: {validadas}
- Taxa de Validação: {(validadas/total_sol*100) if total_sol > 0 else 0:.1f}%
- Validações Realizadas: {total_hist}
""")
```

---

## 🆘 Troubleshooting

### ❌ Erro: "Table does not exist"
```bash
# Solução:
python manage.py migrate procedures

# Se persistir:
python manage.py migrate procedures 0016  # Voltar uma migration
python manage.py migrate procedures 0017  # Reaplicar
```

### ❌ Erro: "No such table: procedures_solicitacaovalidacaomatriz"
```bash
# Faltou aplicar a migration
python manage.py migrate
python manage.py migrate procedures
```

### ❌ Erro: "ValidationError: Validador is required"
```python
# Garantir que validador está sendo passado:
from procedures.models import SolicitacaoValidacaoMatriz
from rh.models import Colaborador

validador = Colaborador.objects.get(id=1)
sol = SolicitacaoValidacaoMatriz.objects.create(
    matriz_id=1,
    validador=validador,  # ← Não esqueça!
    status='pendente'
)
```

### ❌ Erro: "ImportError: cannot import name 'validacao_views'"
```bash
# Faltou adicionar ao urls.py:
# Abrir procedures/urls.py

# Adicionar:
from .views import validacao_views

# Nas URLs:
path('validacoes/pendentes/', validacao_views.validacoes_pendentes_view, name='validacoes_pendentes'),
```

### ❌ Solicitação não aparece em "Pendências"
```python
# Verificar se está com status correto:
from procedures.models import SolicitacaoValidacaoMatriz

sol = SolicitacaoValidacaoMatriz.objects.get(id=1)
print(f"Status: {sol.status}")  # Deve ser 'pendente'
print(f"Validador: {sol.validador}")  # Deve ter um validador
```

### ❌ Histórico não está sendo criado
```python
# Verificar se view está salvando:
from procedures.models import HistoricoValidacaoMassa

historicos = HistoricoValidacaoMassa.objects.all()
for h in historicos:
    print(f"{h.matriz.nome} - {h.validador.nome_completo} - {h.executado_em}")
```

---

## 📊 Relatórios Úteis

### **1. Gerar Relatório de Validações**
```bash
python manage.py shell

from procedures.models import SolicitacaoValidacaoMatriz, HistoricoValidacaoMassa
from django.db.models import Count, Q

# Por status
print("\n=== SOLICITAÇÕES POR STATUS ===")
for status_choice in ['pendente', 'validada', 'rejeitada']:
    count = SolicitacaoValidacaoMatriz.objects.filter(status=status_choice).count()
    print(f"{status_choice}: {count}")

# Por validador (top 5)
print("\n=== VALIDADORES MAIS ATIVOS ===")
validadores = HistoricoValidacaoMassa.objects.values(
    'validador__nome_completo'
).annotate(total=Count('id')).order_by('-total')[:5]

for v in validadores:
    print(f"{v['validador__nome_completo']}: {v['total']} validações")

# Por matriz (mais validadas)
print("\n=== MATRIZES MAIS VALIDADAS ===")
matrizes = HistoricoValidacaoMassa.objects.values(
    'matriz__nome'
).annotate(total=Count('id')).order_by('-total')[:5]

for m in matrizes:
    print(f"{m['matriz__nome']}: {m['total']} validações")
```

### **2. Exportar para CSV**
```bash
python manage.py shell

import csv
from procedures.models import SolicitacaoValidacaoMatriz

with open('validacoes.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['ID', 'Matriz', 'Solicitante', 'Validador', 'Status', 'Data'])
    
    for sol in SolicitacaoValidacaoMatriz.objects.all():
        writer.writerow([
            sol.id,
            sol.matriz.nome,
            sol.solicitante.nome_completo if sol.solicitante else 'N/A',
            sol.validador.nome_completo,
            sol.get_status_display(),
            sol.criado_em.strftime('%d/%m/%Y %H:%M')
        ])

print("Arquivo validacoes.csv criado!")
```

---

## 🔒 Segurança

### **1. Permissões Recomendadas**
```python
# Em views.py, adicionar verificação:
@login_required
def validacoes_pendentes_view(request):
    try:
        colaborador = request.user.colaborador
    except:
        messages.error(request, 'Usuário sem perfil de colaborador')
        return redirect('home')
    
    # Apenas ver próprias validações
    validacoes = SolicitacaoValidacaoMatriz.objects.filter(
        validador=colaborador,
        status='pendente'
    )
```

### **2. Auditoria**
```python
# Log de quem fez o quê
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE

LogEntry.objects.filter(
    content_type__app_label='procedures'
).order_by('-action_time')
```

---

## 📞 Contato de Suporte

Qualquer dúvida técnica, verifique:
1. `procedures/views/validacao_views.py` - Lógica das views
2. `procedures/models.py` - Estrutura dos modelos
3. `procedures/urls.py` - Configuração de rotas
4. Django logs: `python manage.py runserver` (stderr)

---

**Última atualização**: 29/12/2025  
**Versão**: 1.0  
**Status**: ✅ PRONTO
