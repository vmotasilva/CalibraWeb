"""
Script utilitario para gerar registros de treinamento iniciais.
Uso sugerido:
  1. Atribuir pacotes a colaboradores via admin ou shell.
  2. Rodar: python manage.py shell < scripts/gerar_registros_treinamento.py

Opcoes de configuracao (edite abaixo):
  FILTRAR_SETOR_NOMES: lista de nomes de setor para limitar a geracao.
  INCLUIR_COLABORADORES_SEM_PACOTE: se True gera registros para TODOS os procedimentos dos pacotes mesmo se colaborador ainda nao tem o pacote (usa todos pacotes).
"""

FILTRAR_SETOR_NOMES = []  # Ex: ["SURFACING", "COATING"]
INCLUIR_COLABORADORES_SEM_PACOTE = False

from datetime import date
from qms.models import Colaborador, RegistroTreinamento, PacoteTreinamento

def main():
    pacotes = PacoteTreinamento.objects.all()
    if not pacotes.exists():
        print("Nenhum pacote cadastrado. Saindo.")
        return

    qs_colabs = Colaborador.objects.filter(is_active=True)
    if FILTRAR_SETOR_NOMES:
        qs_colabs = qs_colabs.filter(setor__nome__in=FILTRAR_SETOR_NOMES)

    total_registros_criados = 0
    total_colabs = qs_colabs.count()
    print(f"Processando {total_colabs} colaboradores ativos...")

    for colab in qs_colabs.iterator():
        # Determina pacotes relevantes
        if INCLUIR_COLABORADORES_SEM_PACOTE:
            pacotes_relevantes = pacotes
        else:
            pacotes_relevantes = colab.pacotes_treinamento.all()
        if not pacotes_relevantes.exists():
            continue

        procedimentos_target = set()
        for pacote in pacotes_relevantes:
            for proc in pacote.procedimentos.all():
                if proc.aplica_treinamento:
                    procedimentos_target.add(proc)

        for proc in procedimentos_target:
            obj, created = RegistroTreinamento.objects.get_or_create(
                colaborador=colab,
                procedimento=proc,
                defaults={
                    "revisao_treinada": "PENDENTE",
                    "data_treinamento": date.today(),
                },
            )
            if created:
                total_registros_criados += 1
    print(f"Registros de treinamento criados: {total_registros_criados}")


if __name__ == "__main__":
    main()
