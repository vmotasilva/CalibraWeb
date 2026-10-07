# -*- coding: utf-8 -*-
"""
Serviço de Governança QMS / ISO 13485 para Diagramas e Fluxogramas
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from ..models_diagram import DiagramaVersao, StatusDiagrama


def _exige_segregacao() -> bool:
    """Quem submete a revisão não pode aprová-la (padrão: ativo). Desative com DIAGRAMAS_EXIGIR_SEGREGACAO_FUNCOES = False."""
    return getattr(settings, 'DIAGRAMAS_EXIGIR_SEGREGACAO_FUNCOES', True)


class DiagramaQMSService:
    """Gerencia o ciclo de vida documental e integridade das versões de fluxogramas."""

    @staticmethod
    def submeter_para_aprovacao(versao: DiagramaVersao, usuario) -> DiagramaVersao:
        if versao.status != StatusDiagrama.RASCUNHO:
            raise ValidationError(f"Apenas versões em Rascunho podem ser submetidas. Status atual: {versao.get_status_display()}")

        nodes = (versao.dados_topologia or {}).get('nodes', [])
        if not nodes:
            raise ValidationError("Não é possível submeter um fluxograma sem nós ou atividades configuradas.")

        versao.status = StatusDiagrama.EM_APROVACAO
        versao.submetido_por = usuario
        versao.data_submissao = timezone.now()
        versao.save(update_fields=['status', 'submetido_por', 'data_submissao', 'atualizado_em'])
        return versao

    @staticmethod
    def devolver_para_ajustes(versao: DiagramaVersao, usuario, motivo: str) -> DiagramaVersao:
        """Reprova a revisão em aprovação e a devolve ao elaborador como Rascunho (com justificativa)."""
        if versao.status != StatusDiagrama.EM_APROVACAO:
            raise ValidationError("Apenas versões Em Aprovação podem ser devolvidas para ajustes.")
        if not motivo or len(motivo.strip()) < 5:
            raise ValidationError("É obrigatório informar o motivo da devolução (mínimo de 5 caracteres).")

        versao.status = StatusDiagrama.RASCUNHO
        versao.motivo_devolucao = motivo.strip()
        versao.save(update_fields=['status', 'motivo_devolucao', 'atualizado_em'])
        return versao

    @staticmethod
    def aprovar_versao(versao: DiagramaVersao, usuario_aprovador) -> DiagramaVersao:
        # A aprovação só ocorre após a submissão formal (Rascunho -> Em Aprovação -> Aprovado)
        if versao.status != StatusDiagrama.EM_APROVACAO:
            raise ValidationError("Somente versões Em Aprovação podem ser aprovadas. Submeta a revisão antes.")

        if (_exige_segregacao() and versao.submetido_por_id
                and versao.submetido_por_id == getattr(usuario_aprovador, 'pk', None)):
            raise ValidationError("Segregação de funções: quem submeteu a revisão não pode aprová-la. Solicite a outro aprovador.")

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

        if versao_vigente.status != StatusDiagrama.APROVADO:
            raise ValidationError("Só é possível criar nova revisão a partir de uma versão Aprovada vigente.")

        with transaction.atomic():
            # Trava as revisões do diagrama para evitar duas revisões criadas em paralelo
            versoes = list(DiagramaVersao.objects.select_for_update().filter(diagrama=versao_vigente.diagrama))

            if any(v.status in (StatusDiagrama.RASCUNHO, StatusDiagrama.EM_APROVACAO) for v in versoes):
                raise ValidationError("Já existe uma revisão em andamento (Rascunho ou Em Aprovação) para este diagrama.")

            ultima_revisao = max(v.revisao for v in versoes)
            return DiagramaVersao.objects.create(
                diagrama=versao_vigente.diagrama,
                revisao=ultima_revisao + 1,
                status=StatusDiagrama.RASCUNHO,
                dados_topologia=versao_vigente.dados_topologia,  # Clona topologia atual
                motivo_revisao=motivo.strip()
            )
