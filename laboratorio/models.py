from datetime import timedelta
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def _normalizar_texto_categoria(valor):
    texto = unicodedata.normalize("NFKD", valor or "")
    return "".join(caractere for caractere in texto if not unicodedata.combining(caractere)).lower().strip()


class CategoriaLaboratorio(models.Model):
    IMPACTO_BAIXO = "BAIXO"
    IMPACTO_MEDIO = "MEDIO"
    IMPACTO_ALTO = "ALTO"
    IMPACTO_CRITICO = "CRITICO"

    IMPACTO_CHOICES = [
        (IMPACTO_BAIXO, "Baixo"),
        (IMPACTO_MEDIO, "Medio"),
        (IMPACTO_ALTO, "Alto"),
        (IMPACTO_CRITICO, "Critico"),
    ]

    nome = models.CharField(max_length=150, unique=True, verbose_name="Categoria")
    impacto = models.CharField(
        max_length=20,
        choices=IMPACTO_CHOICES,
        default=IMPACTO_MEDIO,
        verbose_name="Impacto padrao",
    )
    descricao = models.TextField(blank=True, verbose_name="Descricao")
    ativo = models.BooleanField(default=True, verbose_name="Ativa")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Categoria de ocorrencia do laboratorio"
        verbose_name_plural = "Categorias de ocorrencia do laboratorio"

    def __str__(self):
        return self.nome

    @property
    def nome_normalizado(self):
        return _normalizar_texto_categoria(self.nome)

    @property
    def exige_colaborador(self):
        return self.nome_normalizado.startswith("falta de colaborador")

    @property
    def exige_maquina(self):
        return self.nome_normalizado.startswith("parada de maquina") or self.nome_normalizado.startswith("parada de manutencao")


from rh.models import Colaborador
from maquinas.models import Maquina

class OcorrenciaLaboratorio(models.Model):
    categoria = models.ForeignKey(
        CategoriaLaboratorio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias",
        verbose_name="Categoria",
    )
    assunto = models.CharField(max_length=200, verbose_name="Assunto")
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_laboratorio_colaborador",
        verbose_name="Colaborador (se aplicável)",
    )
    maquina = models.ForeignKey(
        Maquina,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_laboratorio_maquina",
        verbose_name="Máquina (se aplicável)",
    )
    detalhamento = models.TextField(verbose_name="Detalhamento")
    consequencias = models.TextField(blank=True, verbose_name="Consequencias")
    impacto = models.CharField(
        max_length=20,
        choices=CategoriaLaboratorio.IMPACTO_CHOICES,
        default=CategoriaLaboratorio.IMPACTO_MEDIO,
        verbose_name="Impacto",
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_laboratorio",
        verbose_name="Responsavel",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_laboratorio_criadas",
        verbose_name="Criado por",
    )
    data_abertura = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data e hora da abertura",
    )
    data_encerramento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data e hora do encerramento",
    )
    perda_producao = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Perda de producao",
    )
    unidade_perda_producao = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Unidade da perda de producao",
    )
    horas_indisponibilidade = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Horas de indisponibilidade",
    )
    impacto_financeiro = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Impacto financeiro estimado",
    )
    observacoes_encerramento = models.TextField(
        blank=True,
        verbose_name="Observacoes do encerramento",
    )
    duracao = models.DurationField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Duracao da ocorrencia",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_abertura"]
        verbose_name = "Ocorrencia do laboratorio"
        verbose_name_plural = "Ocorrencias do laboratorio"
        indexes = [
            models.Index(fields=["data_abertura"]),
            models.Index(fields=["impacto"]),
        ]

    def __str__(self):
        return self.assunto

    def clean(self):
        errors = {}

        if not self.assunto and self.categoria:
            self.assunto = self.categoria.nome

        if not self.assunto:
            errors["assunto"] = "Informe um assunto ou selecione uma categoria."

        if self.data_encerramento and self.data_encerramento <= self.data_abertura:
            errors["data_encerramento"] = "O encerramento deve ser posterior a abertura."

        if not self.impacto and self.categoria:
            self.impacto = self.categoria.impacto

        if self.categoria and self.categoria.exige_colaborador and not self.colaborador:
            errors["colaborador"] = "Selecione o colaborador vinculado a esta ocorrencia."

        if self.categoria and self.categoria.exige_maquina and not self.maquina:
            errors["maquina"] = "Selecione a maquina vinculada a esta ocorrencia."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.categoria and not self.assunto:
            self.assunto = self.categoria.nome

        if self.categoria and not self.impacto:
            self.impacto = self.categoria.impacto

        self.duracao = None
        if self.data_abertura and self.data_encerramento:
            self.duracao = self.data_encerramento - self.data_abertura

        super().save(*args, **kwargs)

    @property
    def status(self):
        return "Encerrada" if self.data_encerramento else "Aberta"

    @property
    def impacto_badge_class(self):
        return {
            CategoriaLaboratorio.IMPACTO_BAIXO: "success",
            CategoriaLaboratorio.IMPACTO_MEDIO: "warning text-dark",
            CategoriaLaboratorio.IMPACTO_ALTO: "danger",
            CategoriaLaboratorio.IMPACTO_CRITICO: "dark",
        }.get(self.impacto, "secondary")

    @property
    def possui_impacto_registrado(self):
        return any(
            valor not in (None, "")
            for valor in (
                self.perda_producao,
                self.horas_indisponibilidade,
                self.impacto_financeiro,
                self.observacoes_encerramento,
            )
        )

    @staticmethod
    def formatar_duracao(valor):
        if not valor:
            return "-"

        total_segundos = int(valor.total_seconds())
        total_segundos = abs(total_segundos)
        dias, resto = divmod(total_segundos, 86400)
        horas, resto = divmod(resto, 3600)
        minutos, _segundos = divmod(resto, 60)

        partes = []
        if dias:
            partes.append(f"{dias}d")
        if horas:
            partes.append(f"{horas}h")
        partes.append(f"{minutos}min")
        return " ".join(partes)

    @property
    def duracao_formatada(self):
        valor = self.duracao
        if not valor and self.data_abertura and not self.data_encerramento:
            valor = timezone.now() - self.data_abertura
        return self.formatar_duracao(valor)


class OcorrenciaLaboratorioAnotacao(models.Model):
    ocorrencia = models.ForeignKey(
        OcorrenciaLaboratorio,
        on_delete=models.CASCADE,
        related_name="anotacoes_registradas",
        verbose_name="Ocorrencia",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anotacoes_ocorrencias_laboratorio",
        verbose_name="Responsavel pela anotacao",
    )
    texto = models.TextField(verbose_name="Anotacao")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Data e hora da anotacao")

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "Anotacao da ocorrencia do laboratorio"
        verbose_name_plural = "Anotacoes das ocorrencias do laboratorio"

    def __str__(self):
        return f"Anotacao de {self.autor_display} em {timezone.localtime(self.criado_em).strftime('%d/%m/%Y %H:%M:%S')}"

    @property
    def autor_display(self):
        if not self.usuario:
            return "Usuario nao informado"
        return self.usuario.get_full_name() or self.usuario.username


class TratamentoAntiReflexo(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome do Tratamento")
    cor = models.CharField(max_length=7, default="#0d6efd", verbose_name="Cor de Destaque", help_text="Cor em formato HEX (ex: #ff0000 para vermelho)")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Tratamento Antirreflexo"
        verbose_name_plural = "Tratamentos Antirreflexo"

    def __str__(self):
        return self.nome


class RegraTurnoCoating(models.Model):
    nome = models.CharField(max_length=50, verbose_name="Nome da Regra (Ex: Turno 01)")
    hora_inicio = models.TimeField(verbose_name="Horário de Início")
    hora_fim = models.TimeField(verbose_name="Horário de Fim")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        ordering = ["hora_inicio"]
        verbose_name = "Regra de Turno de Coating"
        verbose_name_plural = "Regras de Turnos de Coating"

    def __str__(self):
        return f"{self.nome} ({self.hora_inicio.strftime('%H:%M')} - {self.hora_fim.strftime('%H:%M')})"


class TurnoCoating(models.Model):
    data = models.DateField(default=timezone.now, verbose_name="Data do Turno")
    regra = models.ForeignKey(RegraTurnoCoating, on_delete=models.PROTECT, verbose_name="Regra de Turno", null=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Responsável pelo Fechamento",
    )

    class Meta:
        ordering = ["-data", "regra__hora_inicio"]
        verbose_name = "Turno Diário de Coating"
        verbose_name_plural = "Turnos Diários de Coating"
        unique_together = [('data', 'regra')]

    def __str__(self):
        if self.regra:
            return f"{self.regra.nome} - {self.data.strftime('%d/%m/%Y')}"
        return f"Turno sem regra - {self.data.strftime('%d/%m/%Y')}"


class RegistroCoating(models.Model):
    LADO_CHOICES = [
        ('CC', 'Côncavo'),
        ('CX', 'Convexo'),
    ]
    turno_coating = models.ForeignKey(
        TurnoCoating, 
        on_delete=models.PROTECT, 
        related_name="registros",
        verbose_name="Turno de Referência"
    )
    maquina = models.ForeignKey(Maquina, on_delete=models.PROTECT, verbose_name="Máquina")
    lote = models.IntegerField(verbose_name="Número do Lote")
    tratamento = models.ForeignKey(TratamentoAntiReflexo, on_delete=models.PROTECT, verbose_name="Tratamento")
    lado = models.CharField(max_length=2, choices=LADO_CHOICES, verbose_name="Lado da Lente")
    
    hora_entrada = models.DateTimeField(null=True, blank=True, verbose_name="Entrada (Data e Hora)")
    hora_saida = models.DateTimeField(null=True, blank=True, verbose_name="Saída (Data e Hora)")
    
    preparacao = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name="preparacoes_coating", verbose_name="Preparação", null=True, blank=True)
    montagem = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name="montagens_coating", verbose_name="Montagem", null=True, blank=True)
    observacao = models.TextField(blank=True, null=True, verbose_name="Observação do Lote")
    
    
    # Manutenções agora são registradas pela tabela ManutencaoRealizadaCoating
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-turno_coating__data", "-hora_entrada", "lote"]
        verbose_name = "Registro de Coating"
        verbose_name_plural = "Registros de Coating"

    def __str__(self):
        return f"Lote {self.lote} - {self.maquina} ({self.get_lado_display()})"


class CicloManutencaoCoating(models.Model):
    TIPO_CHOICES = [
        ('LIMPEZA', 'Limpeza'),
        ('TROCA', 'Troca'),
    ]
    
    CRITERIO_CHOICES = [
        ('LOTES', 'Por Quantidade de Lotes'),
        ('DIAS', 'Por Tempo (Dias Corridos)')
    ]
    
    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name="ciclos_coating", verbose_name="Máquina")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name="Tipo", default='LIMPEZA')
    nome = models.CharField(max_length=100, verbose_name="Nome da Manutenção", default="Manutenção Padrão")
    criterio = models.CharField(max_length=10, choices=CRITERIO_CHOICES, default='LOTES', verbose_name="Critério de Alerta")
    limite_lotes = models.IntegerField(default=10, verbose_name="Limite (Lotes/Dias)")
    
    class Meta:
        verbose_name = "Ciclo de Manutenção de Coating"
        verbose_name_plural = "Ciclos de Manutenção de Coating"
        ordering = ['maquina', 'tipo', 'nome']
        
    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()}) - {self.maquina.codigo}"


class ManutencaoRealizadaCoating(models.Model):
    registro = models.ForeignKey(RegistroCoating, on_delete=models.CASCADE, related_name="manutencoes", verbose_name="Registro de Lote")
    ciclo = models.ForeignKey(CicloManutencaoCoating, on_delete=models.PROTECT, related_name="realizacoes", verbose_name="Manutenção Realizada")
    data_realizacao = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True, null=True, verbose_name="Observações Gerais")

    class Meta:
        verbose_name = "Manutenção Realizada (Coating)"
        verbose_name_plural = "Manutenções Realizadas (Coating)"
        unique_together = ('registro', 'ciclo')

    def __str__(self):
        return f"{self.ciclo.nome} no {self.registro}"

class ItemChecklistCiclo(models.Model):
    ciclo = models.ForeignKey(CicloManutencaoCoating, on_delete=models.CASCADE, related_name="itens_checklist", verbose_name="Ciclo de Manutenção")
    texto = models.CharField(max_length=255, verbose_name="Descrição da Tarefa")
    ordem = models.IntegerField(default=1, verbose_name="Ordem de Exibição")

    class Meta:
        verbose_name = "Item de Checklist de Ciclo"
        verbose_name_plural = "Itens de Checklist de Ciclos"
        ordering = ['ordem', 'id']

    def __str__(self):
        return f"{self.ordem} - {self.texto} ({self.ciclo.nome})"

class RespostaChecklistManutencao(models.Model):
    manutencao = models.ForeignKey(ManutencaoRealizadaCoating, on_delete=models.CASCADE, related_name="respostas_checklist", verbose_name="Manutenção Realizada")
    item = models.ForeignKey(ItemChecklistCiclo, on_delete=models.CASCADE, verbose_name="Item do Checklist")
    feito = models.BooleanField(default=False, verbose_name="Feito?")

    class Meta:
        verbose_name = "Resposta de Checklist"
        verbose_name_plural = "Respostas de Checklist"
        unique_together = ('manutencao', 'item')

    def __str__(self):
        return f"{self.item.texto}: {'Sim' if self.feito else 'Não'}"

class EquipeCoating(models.Model):
    colaborador = models.OneToOneField("rh.Colaborador", on_delete=models.CASCADE, verbose_name="Colaborador")
    pode_preparar = models.BooleanField(default=True, verbose_name="Pode Preparar")
    pode_montar = models.BooleanField(default=True, verbose_name="Pode Montar")
    
    class Meta:
        verbose_name = "Equipe de Coating"
        verbose_name_plural = "Equipe de Coating"
        
    def __str__(self):
        return f"{self.colaborador.nome_completo}"
