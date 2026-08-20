from django.core.management.base import BaseCommand
from auditoria.models import BancoPergunta, RespostaEntrevistaIso, SolicitacaoEvidenciaIso, ItemNorma

class Command(BaseCommand):
    help = "Resgata e consolida solicitações de evidência associando-as à pergunta ativa canônica de cada item da norma."

    def handle(self, *args, **options):
        self.stdout.write("Iniciando resgate e consolidação de solicitações por item...")
        
        # 1. Recuperar respostas de perguntas inativas
        inativas = BancoPergunta.objects.filter(ativa=False)
        for p_inativa in inativas:
            resps = RespostaEntrevistaIso.objects.filter(pergunta=p_inativa)
            if not resps.exists():
                continue
            self.stdout.write(f"Encontrada pergunta inativa ID={p_inativa.id} com {resps.count()} respostas.")
            
            # Procurar pergunta ativa com texto similar ou pelo item
            p_ativa = BancoPergunta.objects.filter(ativa=True, texto_pergunta__iexact=p_inativa.texto_pergunta).first()
            if not p_ativa and p_inativa.itens_norma.exists():
                p_ativa = BancoPergunta.objects.filter(ativa=True, itens_norma__in=p_inativa.itens_norma.all()).first()
                
            if not p_ativa:
                # Tentar associar à primeira pergunta ativa
                p_ativa = BancoPergunta.objects.filter(ativa=True).order_by('id').first()
                
            if p_ativa and p_ativa.id != p_inativa.id:
                self.stdout.write(f"Migrando respostas da inativa {p_inativa.id} -> ativa {p_ativa.id}")
                for resp in resps:
                    resp_ativa, _ = RespostaEntrevistaIso.objects.get_or_create(
                        auditoria=resp.auditoria,
                        pergunta=p_ativa,
                        defaults={'respondida_por': resp.respondida_por}
                    )
                    sols_count = SolicitacaoEvidenciaIso.objects.filter(resposta=resp).count()
                    SolicitacaoEvidenciaIso.objects.filter(resposta=resp).update(resposta=resp_ativa)
                    self.stdout.write(f"  {sols_count} solicitações migradas para auditoria {resp.auditoria_id}")
                    if resp.texto_resposta and not resp_ativa.texto_resposta:
                        resp_ativa.texto_resposta = resp.texto_resposta
                        resp_ativa.save(update_fields=['texto_resposta'])
                    resp.delete()
                    
        # 2. Re-vincular perguntas ativas aos seus Itens da Norma
        for item in ItemNorma.objects.prefetch_related('perguntas_vinculadas').all():
            perguntas_item = list(item.perguntas_vinculadas.filter(ativa=True).order_by('id'))
            if len(perguntas_item) > 1:
                p_canon = perguntas_item[0]
                for p_dup in perguntas_item[1:]:
                    self.stdout.write(f"Consolidando duplicata de item {item.referencia}: P{p_dup.id} -> P{p_canon.id}")
                    for resp_dup in RespostaEntrevistaIso.objects.filter(pergunta=p_dup):
                        resp_canon, _ = RespostaEntrevistaIso.objects.get_or_create(
                            auditoria=resp_dup.auditoria,
                            pergunta=p_canon,
                            defaults={'respondida_por': resp_dup.respondida_por}
                        )
                        SolicitacaoEvidenciaIso.objects.filter(resposta=resp_dup).update(resposta=resp_canon)
                        if resp_dup.texto_resposta and not resp_canon.texto_resposta:
                            resp_canon.texto_resposta = resp_dup.texto_resposta
                            resp_canon.save(update_fields=['texto_resposta'])
                        resp_dup.delete()

        self.stdout.write(self.style.SUCCESS("Consolidação finalizada com sucesso!"))

