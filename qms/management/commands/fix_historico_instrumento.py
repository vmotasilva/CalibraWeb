from django.core.management.base import BaseCommand
from qms.models import HistoricoCalibracao, Instrumento

class Command(BaseCommand):
    help = 'Associa históricos antigos ao instrumento correto via número de certificado ou tag.'

    def handle(self, *args, **options):
        # Exemplo: associa todos os históricos sem instrumento ao instrumento LE-02
        instrumento = Instrumento.objects.filter(tag='LE-02').first()
        if not instrumento:
            self.stdout.write(self.style.ERROR('Instrumento LE-02 não encontrado.'))
            return
        count = 0
        for hist in HistoricoCalibracao.objects.filter(instrumento__isnull=True):
            hist.instrumento = instrumento
            hist.save()
            count += 1
        self.stdout.write(self.style.SUCCESS(f'{count} históricos atualizados para instrumento {instrumento.tag}'))
