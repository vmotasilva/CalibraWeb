from datetime import date
from rh.models import Colaborador

hoje = date.today()
colabs_ferias = Colaborador.objects.filter(
    ferias__aprovada=True,
    ferias__data_inicio__lte=hoje,
    ferias__data_fim__gte=hoje
).distinct()

print("Colaboradores atualmente em férias:")
for c in colabs_ferias:
    print(f"{c.id} - {c.nome_completo} ({c.matricula})")
print(f"Total: {colabs_ferias.count()}")
