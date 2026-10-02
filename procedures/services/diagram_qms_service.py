# -*- coding: utf-8 -*-
"""
Serviço de Governança QMS / ISO 13485 para Diagramas e Fluxogramas
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from ..models_diagram import DiagramaVersao, StatusDiagrama


class DiagramaQMSService:
    """Gerencia o ciclo de vida documental e integridade das versões de fluxogramas."""

    @staticmethod
    def submeter_para_aprovacao(versao: DiagramaVersao, usuario) -> DiagramaVersao:
        if versao.status != StatusDiagrama.RASCUNHO:
            raise ValidationError(f"Apenas versões em Rascunho podem ser submetidas. Status atual: {versao.get_status_display()}")

        nodes = versao.dados_topologia.get('nodes', [])
        if not nodes:
            raise ValidationError("Não é possível submeter um fluxograma sem nós ou atividades configuradas.")

        versao.status = StatusDiagrama.EM_APROVACAO
        versao.save(update_fields=['status', 'atualizado_em'])
        return versao

    @staticmethod
    def aprovar_versao(versao: DiagramaVersao, usuario_aprovador) -> DiagramaVersao:
        if versao.status not in [StatusDiagrama.EM_APROVACAO, StatusDiagrama.RASCUNHO]:
            raise ValidationError("Esta versão não está elegível para aprovação.")

        with transaction.atomic():
            # 1. Torna obsoletas versões anteriormente aprovadas do mesmo diagrama
            DiagramaVersao.objects.filter(
                diagrama=versao.diagrama,
                status=StatusDiagrama.APROVADO
            ).update(status=StatusDiagrama.OBSOLETO)

            # 2. Registra assinatura e status de aprovação
            versao.status = StatusDiagrama.APROVADO
            versao.aprovado_por = usuario_aprovador
            versao.data_aprovacao = timezone.now()
            versao.save(update_fields=['status', 'aprovado_por', 'data_aprovacao', 'atualizado_em'])

        return versao

    @staticmethod
    def criar_nova_revisao(versao_vigente: DiagramaVersao, usuario, motivo: str) -> DiagramaVersao:
        """Cria uma nova revisão (ex: R01, R02) a partir da versão aprovada vigente."""
        if not motivo or len(motivo.strip()) < 5:
            raise ValidationError("É obrigatório fornecer a justificativa/motivo da revisão.")

        diagrama = versao_vigente.diagrama
        ultima_revisao = diagrama.versoes.order_by('-revisao').first().revisao

        nova_versao = DiagramaVersao.objects.create(
            diagrama=diagrama,
            revisao=ultima_revisao + 1,
            status=StatusDiagrama.RASCUNHO,
            dados_topologia=versao_vigente.dados_topologia,  # Clona topologia atual
            motivo_revisao=motivo.strip()
        )
        return nova_versao
