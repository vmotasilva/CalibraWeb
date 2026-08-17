new_model = """
class AvaliacaoFinalRequisitoIso(models.Model):
    CLASSIFICACAO_CHOICES = [
        ("C", "Conforme"),
        ("NC", "Não Conforme"),
        ("NA", "Não Aplicável"),
        ("OM", "Oportunidade de Melhoria"),
        ("P", "Pendente"),
    ]
    auditoria = models.ForeignKey(AuditoriaIso, on_delete=models.CASCADE, related_name="avaliacoes_finais")
    item_norma = models.ForeignKey(ItemNorma, on_delete=models.CASCADE, related_name="avaliacoes_finais")
    classificacao = models.CharField(max_length=2, choices=CLASSIFICACAO_CHOICES)
    justificativa = models.TextField(blank=True, verbose_name="Argumentação / Justificativa da Reversão")
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Avaliação Final do Requisito ISO"
        verbose_name_plural = "Avaliações Finais dos Requisitos ISO"
        unique_together = ('auditoria', 'item_norma')

    def __str__(self):
        return f"{self.auditoria} - {self.item_norma.referencia} ({self.classificacao})"
"""

with open('auditoria/models.py', 'a', encoding='utf-8') as f:
    f.write(new_model)
