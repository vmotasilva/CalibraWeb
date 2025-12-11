"""
Utilitários para gerenciar o histórico de colaboradores
"""
from django.utils import timezone
from django.contrib.auth.models import User
from .models import (
    Colaborador, HistoricoSetor, HistoricoPosto,
    HistoricoSalario, HistoricoColaborador
)


class GerenciadorHistoricoColaborador:
    """
    Classe para gerenciar mudanças de colaborador de forma organizada
    Evita duplicação de registros pelos signals
    """

    @staticmethod
    def registrar_mudanca_setor(colaborador, setor_novo, motivo="", usuario=None, data_efetiva=None):
        """Registra uma mudança de setor"""
        setor_anterior = colaborador.setor
        
        HistoricoSetor.objects.create(
            colaborador=colaborador,
            setor_anterior=setor_anterior,
            setor_novo=setor_novo,
            motivo=motivo,
            data_efetiva=data_efetiva or timezone.now().date(),
            registrado_por=usuario
        )
        
        HistoricoColaborador.objects.create(
            colaborador=colaborador,
            tipo_mudanca="SETOR",
            descricao=f"Setor alterado de {setor_anterior} para {setor_novo}. Motivo: {motivo}",
            dados_anteriores={"setor": str(setor_anterior) if setor_anterior else None},
            dados_novos={"setor": str(setor_novo) if setor_novo else None},
            data_efetiva=data_efetiva or timezone.now().date(),
            registrado_por=usuario
        )

    @staticmethod
    def registrar_mudanca_cargo(colaborador, cargo_novo, motivo="", usuario=None, data_efetiva=None):
        """Registra uma mudança de cargo"""
        cargo_anterior = colaborador.cargo
        
        HistoricoPosto.objects.create(
            colaborador=colaborador,
            cargo_anterior=cargo_anterior,
            cargo_novo=cargo_novo,
            motivo=motivo,
            data_efetiva=data_efetiva or timezone.now().date(),
            registrado_por=usuario
        )
        
        HistoricoColaborador.objects.create(
            colaborador=colaborador,
            tipo_mudanca="CARGO",
            descricao=f"Cargo alterado de {cargo_anterior} para {cargo_novo}. Motivo: {motivo}",
            dados_anteriores={"cargo": cargo_anterior},
            dados_novos={"cargo": cargo_novo},
            data_efetiva=data_efetiva or timezone.now().date(),
            registrado_por=usuario
        )

    @staticmethod
    def registrar_mudanca_salario(colaborador, salario_novo, motivo="", usuario=None, data_efetiva=None):
        """Registra uma mudança de salário"""
        salario_anterior = colaborador.salario
        diferenca = salario_novo - salario_anterior if salario_novo and salario_anterior else None
        
        HistoricoSalario.objects.create(
            colaborador=colaborador,
            salario_anterior=salario_anterior,
            salario_novo=salario_novo,
            diferenca=diferenca,
            motivo=motivo,
            data_efetiva=data_efetiva or timezone.now().date(),
            registrado_por=usuario
        )
        
        HistoricoColaborador.objects.create(
            colaborador=colaborador,
            tipo_mudanca="SALARIO",
            descricao=f"Salário alterado de R$ {salario_anterior} para R$ {salario_novo}. Motivo: {motivo}",
            dados_anteriores={"salario": float(salario_anterior) if salario_anterior else None},
            dados_novos={"salario": float(salario_novo)},
            data_efetiva=data_efetiva or timezone.now().date(),
            registrado_por=usuario
        )

    @staticmethod
    def registrar_mudanca_turno(colaborador, turno_novo, motivo="", usuario=None, data_efetiva=None):
        """Registra uma mudança de turno"""
        turno_anterior = colaborador.turno
        
        HistoricoColaborador.objects.create(
            colaborador=colaborador,
            tipo_mudanca="TURNO",
            descricao=f"Turno alterado de {turno_anterior} para {turno_novo}. Motivo: {motivo}",
            dados_anteriores={"turno": turno_anterior},
            dados_novos={"turno": turno_novo},
            data_efetiva=data_efetiva or timezone.now().date(),
            registrado_por=usuario
        )

    @staticmethod
    def registrar_mudanca_status(colaborador, ativo, motivo="", usuario=None):
        """Registra uma mudança de status (ativo/inativo)"""
        status_anterior = "Ativo" if colaborador.is_active else "Inativo"
        status_novo = "Ativo" if ativo else "Inativo"
        
        HistoricoColaborador.objects.create(
            colaborador=colaborador,
            tipo_mudanca="STATUS",
            descricao=f"Status alterado de {status_anterior} para {status_novo}. Motivo: {motivo}",
            dados_anteriores={"is_active": colaborador.is_active},
            dados_novos={"is_active": ativo},
            data_efetiva=timezone.now().date(),
            registrado_por=usuario
        )

    @staticmethod
    def obter_historico_resumido(colaborador):
        """Retorna um resumo das mudanças mais recentes do colaborador"""
        return {
            "ultima_mudanca_setor": colaborador.get_ultimo_setor_historico(),
            "ultima_mudanca_cargo": colaborador.get_ultimo_cargo_historico(),
            "ultima_mudanca_salario": colaborador.get_ultimo_salario_historico(),
            "historico_geral_count": colaborador.historico_geral.count(),
        }
