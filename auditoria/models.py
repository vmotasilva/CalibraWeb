from django.conf import settings
from django.db import models


class ModeloAuditoria(models.Model):
    PERIODICIDADE_CHOICES = [
        ("UNICA", "Aplicação Única"),
        ("DIARIA", "Diária"),
        ("SEMANAL", "Semanal"),
        ("QUINZENAL", "Quinzenal"),
        ("MENSAL", "Mensal"),
        ("TRIMESTRAL", "Trimestral"),
        ("SEMESTRAL", "Semestral"),
        ("ANUAL", "Anual"),
    ]
    
    DIA_SEMANA_CHOICES = [
        ("SEGUNDA", "Segunda-feira"),
        ("TERCA", "Terça-feira"),
        ("QUARTA", "Quarta-feira"),
        ("QUINTA", "Quinta-feira"),
        ("SEXTA", "Sexta-feira"),
        ("SABADO", "Sábado"),
        ("DOMINGO", "Domingo"),
    ]

    nome = models.CharField(max_length=150, unique=True)
    objeto_auditoria = models.TextField(verbose_name="Objeto da Auditoria")
    link_sharepoint = models.URLField(blank=True, verbose_name="Link SharePoint")
    periodicidade = models.CharField(max_length=20, choices=PERIODICIDADE_CHOICES, default="MENSAL")
    
    # Campos de referência para periodicidade
    dia_semana = models.CharField(
        max_length=10, 
        choices=DIA_SEMANA_CHOICES, 
        blank=True, 
        null=True,
        verbose_name="Dia da Semana",
        help_text="Para periodicidade semanal"
    )
    dias_quinzenal = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Dias da Quinzena",
        help_text="Dois dias do mês separados por vírgula (ex: 1,16)"
    )
    dia_mes = models.IntegerField(
        blank=True,
        null=True,
        verbose_name="Dia do Mês",
        help_text="Dia do mês para execução (1-31)"
    )
    
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modelos_auditoria_responsavel",
        verbose_name="Responsável pela Auditoria",
        help_text="Usuário responsável pela realização da auditoria"
    )
    
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modelo de Auditoria"
        verbose_name_plural = "Modelos de Auditoria"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
    
    def get_periodicidade_completa(self):
        """Retorna descrição completa da periodicidade incluindo referências"""
        base = self.get_periodicidade_display()
        
        if self.periodicidade == 'SEMANAL' and self.dia_semana:
            dia_label = dict(self.DIA_SEMANA_CHOICES).get(self.dia_semana, self.dia_semana)
            return f"{base} ({dia_label})"
        elif self.periodicidade == 'QUINZENAL' and self.dias_quinzenal:
            return f"{base} (dias {self.dias_quinzenal})"
        elif self.periodicidade in ['MENSAL', 'TRIMESTRAL', 'SEMESTRAL', 'ANUAL'] and self.dia_mes:
            return f"{base} (dia {self.dia_mes})"
        
        return base


class PerguntaAuditoria(models.Model):
    TIPO_RESPOSTA_CHOICES = [
        ("SIM_NAO", "Sim/Não"),
        ("NUMERO", "Número inteiro"),
        ("DECIMAL", "Número decimal"),
    ]

    modelo = models.ForeignKey(
        ModeloAuditoria,
        on_delete=models.CASCADE,
        related_name="perguntas",
        verbose_name="Modelo",
    )
    pergunta = models.CharField(max_length=255)
    tipo_resposta = models.CharField(max_length=20, choices=TIPO_RESPOSTA_CHOICES, default="SIM_NAO")
    ordem = models.PositiveIntegerField(default=1)
    obrigatoria = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Pergunta da Auditoria"
        verbose_name_plural = "Perguntas da Auditoria"
        ordering = ["modelo__nome", "ordem", "id"]

    def __str__(self):
        return f"{self.modelo.nome} - {self.pergunta}"


class RegistroAuditoria(models.Model):
    modelo = models.ForeignKey(
        ModeloAuditoria,
        on_delete=models.PROTECT,
        related_name="registros",
        verbose_name="Modelo",
    )
    data_auditoria = models.DateField(verbose_name="Data da Auditoria")
    periodo_inicio = models.DateField(verbose_name="Período Inicial")
    periodo_fim = models.DateField(verbose_name="Período Final")
    avaliador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias_realizadas",
    )
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Auditoria"
        verbose_name_plural = "Registros de Auditoria"
        ordering = ["-data_auditoria", "-id"]

    def __str__(self):
        return f"{self.modelo.nome} - {self.data_auditoria:%d/%m/%Y}"


class RespostaAuditoria(models.Model):
    registro = models.ForeignKey(
        RegistroAuditoria,
        on_delete=models.CASCADE,
        related_name="respostas",
    )
    pergunta = models.ForeignKey(
        PerguntaAuditoria,
        on_delete=models.PROTECT,
        related_name="respostas",
    )
    valor = models.TextField(blank=True)

    class Meta:
        verbose_name = "Resposta de Auditoria"
        verbose_name_plural = "Respostas de Auditoria"
        ordering = ["registro", "pergunta__ordem", "id"]
        unique_together = ("registro", "pergunta")

    def __str__(self):
        return f"{self.registro} - {self.pergunta.pergunta[:60]}"
