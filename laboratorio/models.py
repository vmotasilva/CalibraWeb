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

    # Mix de serviço: lote inserido no meio de outro na mesma máquina. O usuário confirma a
    # sobreposição de horários ao salvar; ciclos confirmados não contam como conflito na Auditoria.
    mix_servico = models.BooleanField(default=False, verbose_name="Mix de serviço")
    mix_servico_confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Mix de serviço confirmado por",
    )
    mix_servico_confirmado_em = models.DateTimeField(null=True, blank=True, verbose_name="Mix de serviço confirmado em")

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
        ('VERIFICACAO', 'Verificação')
    ]
    
    CRITERIO_CHOICES = [
        ('LOTES', 'Por Quantidade de Lotes'),
        ('DIAS', 'Por Tempo (Dias Corridos)'),
        ('DIARIO', 'Diário (1x ao Dia)'),
        ('SEMANAL', 'Semanal (1x na Semana)'),
        ('QUINZENAL', 'Quinzenal (1x na Quinzena)'),
        ('MENSAL', 'Mensal (1x no Mês)'),
        ('LIVRE', 'Sem Periodicidade (Livre)')
    ]
    
    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name="ciclos_coating", verbose_name="Máquina")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo", default='LIMPEZA')
    nome = models.CharField(max_length=100, verbose_name="Nome da Manutenção", default="Manutenção Padrão")
    criterio = models.CharField(max_length=10, choices=CRITERIO_CHOICES, default='LOTES', verbose_name="Critério de Alerta")
    limite_lotes = models.IntegerField(default=1, verbose_name="Limite de Lotes/Dias")
    
    # Campos exclusivos para tipo VERIFICACAO
    valor_minimo = models.FloatField(null=True, blank=True, verbose_name="Valor Mínimo Aceitável")
    valor_maximo = models.FloatField(null=True, blank=True, verbose_name="Valor Máximo Aceitável")

    # Novos campos
    tratamentos_especificos = models.ManyToManyField(
        'TratamentoAntiReflexo', 
        blank=True, 
        verbose_name="Tratamentos Específicos (Opcional)",
        help_text="Se selecionado, a manutenção só será cobrada e contará lotes que possuam estes tratamentos."
    )
    ordem = models.IntegerField(default=0, verbose_name="Ordem de Exibição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        verbose_name = "Ciclo de Manutenção de Coating"
        verbose_name_plural = "Ciclos de Manutenção de Coating"
        ordering = ['maquina', 'ordem', 'tipo', 'nome']
        
    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()}) - {self.maquina.codigo}"


class ManutencaoRealizadaCoating(models.Model):
    registro = models.ForeignKey(RegistroCoating, on_delete=models.CASCADE, related_name="manutencoes", verbose_name="Registro de Lote")
    ciclo = models.ForeignKey(CicloManutencaoCoating, on_delete=models.PROTECT, related_name="realizacoes", verbose_name="Manutenção Realizada")
    data_realizacao = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True, null=True, verbose_name="Observações Gerais")
    valor_aferido = models.FloatField(null=True, blank=True, verbose_name="Valor Aferido (Verificações)")

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


# ==============================================================================
# TMS - TEMPOS E MOVIMENTOS / CAPACIDADE & PREVISÃO DE PRODUÇÃO
# ==============================================================================

class FluxoProcessoTMS(models.Model):
    UNIDADE_PECAS = "PECAS"
    UNIDADE_PARES = "PARES"
    UNIDADE_LOTES = "LOTES"

    UNIDADE_CHOICES = [
        (UNIDADE_PECAS, "Peças / Unidades"),
        (UNIDADE_PARES, "Pares"),
        (UNIDADE_LOTES, "Lotes"),
    ]

    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome do Fluxo / Linha de Produção")
    codigo = models.CharField(max_length=50, blank=True, verbose_name="Código / Identificador")
    descricao = models.TextField(blank=True, verbose_name="Descrição do Processo")
    horas_trabalho_dia = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=8.8,
        verbose_name="Horas de Trabalho por Dia / Turno",
        help_text="Jornada diária líquida para cálculo da capacidade diária (ex: 8.80h)",
    )
    dias_trabalho_mes = models.IntegerField(default=22, verbose_name="Dias Úteis no Mês")
    unidade_medida = models.CharField(
        max_length=20,
        choices=UNIDADE_CHOICES,
        default=UNIDADE_PECAS,
        verbose_name="Unidade Padrão",
    )
    fator_conversao_par = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.0,
        verbose_name="Fator de Conversão Par (Peças por Par)",
        help_text="Ex: 2 peças por par de lentes",
    )
    tamanho_padrao_lote = models.IntegerField(
        default=1,
        verbose_name="Tamanho Padrão do Lote (Peças)",
        help_text="Quantidade média de peças processadas por lote",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Fluxo de Produção TMS"
        verbose_name_plural = "Fluxos de Produção TMS"

    def __str__(self):
        return self.nome

    @property
    def total_etapas_ativas(self):
        return self.etapas.filter(ativo=True).count()

    def calcular_metricas(self, etapas_override=None):
        """
        Calcula capacidade horária/diária de cada etapa, identifica o posto gargalo,
        calcula a taxa de balanceamento de linha e tempos consolidados.
        
        Permite override para simulações 'what-if' dinâmicas.
        """
        etapas_qs = self.etapas.filter(ativo=True).order_by("ordem", "id")
        etapas_override = etapas_override or {}

        etapas_detalhes = []
        gargalo_etapa = None
        menor_capacidade_hora = None
        soma_tc_efetivo = 0.0
        soma_tc_base = 0.0
        soma_setup_min = 0.0

        for etapa in etapas_qs:
            override = etapas_override.get(str(etapa.id)) or etapas_override.get(etapa.id) or {}
            
            tempo_ciclo = float(override.get("tempo_ciclo_segundos", etapa.tempo_ciclo_segundos) or 1.0)
            tempo_setup = float(override.get("tempo_setup_minutos", etapa.tempo_setup_minutos) or 0.0)
            postos = int(override.get("postos_paralelos", etapa.postos_paralelos) or 1)
            eficiencia = float(override.get("eficiencia_oee", etapa.eficiencia_oee) or 100.0)
            perda = float(override.get("perda_refugo_pct", etapa.perda_refugo_pct) or 0.0)

            postos = max(1, postos)
            eficiencia = max(1.0, min(100.0, eficiencia))
            perda = max(0.0, min(99.0, perda))
            tempo_ciclo = max(0.1, tempo_ciclo)

            # TC efetivo por unidade produzida considerando postos, eficiência e refugo
            fator_eficiencia = eficiencia / 100.0
            fator_aproveitamento = 1.0 - (perda / 100.0)
            tc_efetivo = (tempo_ciclo / postos) / (fator_eficiencia * fator_aproveitamento)

            cap_hora = 3600.0 / tc_efetivo if tc_efetivo > 0 else 0.0
            horas_dia = float(self.horas_trabalho_dia or 8.8)
            cap_dia = cap_hora * horas_dia
            cap_mes = cap_dia * int(self.dias_trabalho_mes or 22)

            fator_par = float(self.fator_conversao_par or 2.0)
            if fator_par <= 0:
                fator_par = 2.0

            item = {
                "id": etapa.id,
                "ordem": etapa.ordem,
                "nome": etapa.nome,
                "codigo": etapa.codigo,
                "tipo_posto": etapa.tipo_posto,
                "tipo_posto_display": etapa.get_tipo_posto_display(),
                "maquina_codigo": etapa.maquina.codigo if etapa.maquina else None,
                "maquina_nome": str(etapa.maquina) if etapa.maquina else None,
                "tempo_ciclo_segundos": tempo_ciclo,
                "tempo_setup_minutos": tempo_setup,
                "postos_paralelos": postos,
                "eficiencia_oee": eficiencia,
                "perda_refugo_pct": perda,
                "tc_efetivo_segundos": round(tc_efetivo, 2),
                "capacidade_hora_pecas": round(cap_hora, 1),
                "capacidade_dia_pecas": int(round(cap_dia)),
                "capacidade_mes_pecas": int(round(cap_mes)),
                "capacidade_hora_pares": round(cap_hora / fator_par, 1),
                "capacidade_dia_pares": int(round(cap_dia / fator_par)),
                "capacidade_mes_pares": int(round(cap_mes / fator_par)),
                "is_gargalo": False,
                "utilizacao_pct": 0.0,
            }

            etapas_detalhes.append(item)
            soma_tc_efetivo += tc_efetivo
            soma_tc_base += tempo_ciclo
            soma_setup_min += tempo_setup

            if menor_capacidade_hora is None or cap_hora < menor_capacidade_hora:
                menor_capacidade_hora = cap_hora
                gargalo_etapa = item

        # Marcar gargalo e calcular utilização
        capacidade_linha_hora = menor_capacidade_hora if menor_capacidade_hora is not None else 0.0
        capacidade_linha_dia = capacidade_linha_hora * float(self.horas_trabalho_dia or 8.8)
        capacidade_linha_mes = capacidade_linha_dia * int(self.dias_trabalho_mes or 22)
        fator_par = float(self.fator_conversao_par or 2.0)

        for item in etapas_detalhes:
            if gargalo_etapa and item["id"] == gargalo_etapa["id"]:
                item["is_gargalo"] = True
                item["utilizacao_pct"] = 100.0
            else:
                cap_etapa = item["capacidade_hora_pecas"]
                item["utilizacao_pct"] = round((capacidade_linha_hora / cap_etapa * 100.0), 1) if cap_etapa > 0 else 0.0

        n_etapas = len(etapas_detalhes)
        max_tc_efetivo = gargalo_etapa["tc_efetivo_segundos"] if gargalo_etapa else 0.0
        
        eficiencia_linha = 0.0
        if n_etapas > 0 and max_tc_efetivo > 0:
            eficiencia_linha = round((soma_tc_efetivo / (n_etapas * max_tc_efetivo)) * 100.0, 1)

        lead_time_teorico_peca_min = round(soma_tc_base / 60.0, 2)

        return {
            "fluxo_id": self.id,
            "fluxo_nome": self.nome,
            "horas_trabalho_dia": float(self.horas_trabalho_dia or 8.8),
            "dias_trabalho_mes": int(self.dias_trabalho_mes or 22),
            "fator_conversao_par": fator_par,
            "total_etapas": n_etapas,
            "gargalo": gargalo_etapa,
            "capacidade_maxima_hora_pecas": round(capacidade_linha_hora, 1),
            "capacidade_maxima_dia_pecas": int(round(capacidade_linha_dia)),
            "capacidade_maxima_mes_pecas": int(round(capacidade_linha_mes)),
            "capacidade_maxima_hora_pares": round(capacidade_linha_hora / fator_par, 1),
            "capacidade_maxima_dia_pares": int(round(capacidade_linha_dia / fator_par)),
            "capacidade_maxima_mes_pares": int(round(capacidade_linha_mes / fator_par)),
            "eficiencia_balanceamento_pct": eficiencia_linha,
            "lead_time_teorico_unitario_min": lead_time_teorico_peca_min,
            "lead_time_teorico_unitario_seg": round(soma_tc_base, 1),
            "soma_setup_minutos": round(soma_setup_min, 1),
            "etapas": etapas_detalhes,
        }

    def simular_previsao(self, demanda_unidades, tipo_unidade="PECAS", horas_dia_simulada=None, etapas_override=None):
        """
        Calcula a previsão de produção para uma meta especificada de unidades (peças, pares ou lotes).
        Retorna tempo total estimado (horas, dias úteis), ritmo de produção e status de ocupação.
        """
        metricas = self.calcular_metricas(etapas_override=etapas_override)
        demanda_unidades = float(demanda_unidades or 0.0)

        fator_par = float(self.fator_conversao_par or 2.0)
        tamanho_lote = int(self.tamanho_padrao_lote or 1)

        # Converter para peças
        if tipo_unidade == self.UNIDADE_PARES:
            pecas_totais = demanda_unidades * fator_par
            pares_totais = demanda_unidades
            lotes_totais = pecas_totais / tamanho_lote if tamanho_lote > 0 else pecas_totais
        elif tipo_unidade == self.UNIDADE_LOTES:
            pecas_totais = demanda_unidades * tamanho_lote
            pares_totais = pecas_totais / fator_par
            lotes_totais = demanda_unidades
        else: # PECAS
            pecas_totais = demanda_unidades
            pares_totais = pecas_totais / fator_par
            lotes_totais = pecas_totais / tamanho_lote if tamanho_lote > 0 else pecas_totais

        horas_dia = float(horas_dia_simulada or self.horas_trabalho_dia or 8.8)
        cap_linha_hora = metricas["capacidade_maxima_hora_pecas"]

        if cap_linha_hora <= 0 or pecas_totais <= 0:
            return {
                "metricas_base": metricas,
                "demanda_solicitada": demanda_unidades,
                "tipo_unidade": tipo_unidade,
                "pecas_totais": pecas_totais,
                "pares_totais": pares_totais,
                "lotes_totais": lotes_totais,
                "tempo_total_horas": 0.0,
                "dias_uteis_estimados": 0.0,
                "horas_trabalho_dia_usada": horas_dia,
                "tempo_formatado": "0 horas",
            }

        # Lead time da 1ª peça (segundos) + (Q - 1) * TC do gargalo (segundos) + Setup Total (segundos)
        tc_gargalo_efetivo = metricas["gargalo"]["tc_efetivo_segundos"] if metricas["gargalo"] else 1.0
        lead_time_1a_peca_seg = metricas["lead_time_teorico_unitario_seg"]
        setup_total_seg = metricas["soma_setup_minutos"] * 60.0

        if pecas_totais > 1:
            tempo_total_seg = lead_time_1a_peca_seg + ((pecas_totais - 1) * tc_gargalo_efetivo) + setup_total_seg
        else:
            tempo_total_seg = lead_time_1a_peca_seg + setup_total_seg

        tempo_total_horas = round(tempo_total_seg / 3600.0, 2)
        dias_uteis = round(tempo_total_horas / horas_dia, 2) if horas_dia > 0 else 0.0

        # Formatação amigável
        dias_int = int(tempo_total_horas // horas_dia) if horas_dia > 0 else 0
        horas_resto = round(tempo_total_horas - (dias_int * horas_dia), 1)
        partes_texto = []
        if dias_int > 0:
            partes_texto.append(f"{dias_int} dia{'s' if dias_int > 1 else ''}")
        if horas_resto > 0 or not partes_texto:
            partes_texto.append(f"{horas_resto:.1f}h")

        return {
            "metricas_base": metricas,
            "demanda_solicitada": demanda_unidades,
            "tipo_unidade": tipo_unidade,
            "pecas_totais": round(pecas_totais, 1),
            "pares_totais": round(pares_totais, 1),
            "lotes_totais": round(lotes_totais, 1),
            "tempo_total_horas": tempo_total_horas,
            "dias_uteis_estimados": dias_uteis,
            "horas_trabalho_dia_usada": horas_dia,
            "tempo_formatado": " e ".join(partes_texto),
        }


class EtapaProcessoTMS(models.Model):
    TIPO_MANUAL = "MANUAL"
    TIPO_MAQUINA = "MAQUINA"
    TIPO_HIBRIDO = "HIBRIDO"

    TIPO_POSTO_CHOICES = [
        (TIPO_MANUAL, "Manual / Operador"),
        (TIPO_MAQUINA, "Máquina / Automatizado"),
        (TIPO_HIBRIDO, "Híbrido (Máquina + Operador)"),
    ]

    fluxo = models.ForeignKey(
        FluxoProcessoTMS,
        on_delete=models.CASCADE,
        related_name="etapas",
        verbose_name="Fluxo de Produção",
    )
    ordem = models.IntegerField(default=1, verbose_name="Ordem / Sequência")
    nome = models.CharField(max_length=150, verbose_name="Nome da Etapa / Posto")
    codigo = models.CharField(max_length=50, blank=True, verbose_name="Código da Etapa")
    tipo_posto = models.CharField(
        max_length=20,
        choices=TIPO_POSTO_CHOICES,
        default=TIPO_MANUAL,
        verbose_name="Tipo de Posto",
    )
    maquina = models.ForeignKey(
        Maquina,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etapas_tms",
        verbose_name="Máquina Associada (Opcional)",
    )
    tempo_ciclo_segundos = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=60.0,
        verbose_name="Tempo de Ciclo por Unidade (segundos)",
        help_text="Tempo necessário para processar 1 unidade (em segundos)",
    )
    tempo_setup_minutos = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.0,
        verbose_name="Tempo de Setup / Troca (minutos)",
        help_text="Tempo de preparação ou troca de lote/ferramental",
    )
    postos_paralelos = models.IntegerField(
        default=1,
        verbose_name="Qtd de Postos / Operadores em Paralelo",
        help_text="Número de postos ou máquinas trabalhando simultaneamente nesta etapa",
    )
    eficiencia_oee = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=85.0,
        verbose_name="Eficiência Operacional / OEE (%)",
        help_text="Percentual de aproveitamento real (0 a 100%)",
    )
    perda_refugo_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.0,
        verbose_name="Taxa de Perda / Refugo (%)",
        help_text="Percentual estimado de refugo ou retrabalho nesta etapa",
    )
    observacoes = models.TextField(blank=True, verbose_name="Observações Operacionais")
    ativo = models.BooleanField(default=True, verbose_name="Ativa")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem", "id"]
        verbose_name = "Etapa de Processo TMS"
        verbose_name_plural = "Etapas de Processo TMS"

    def __str__(self):
        return f"{self.ordem}. {self.nome} ({self.fluxo.nome})"

    @property
    def tempo_ciclo_minutos(self):
        return round(float(self.tempo_ciclo_segundos or 0.0) / 60.0, 2)

    @property
    def tempo_ciclo_efetivo_segundos(self):
        tempo = float(self.tempo_ciclo_segundos or 1.0)
        postos = max(1, int(self.postos_paralelos or 1))
        eficiencia = max(1.0, float(self.eficiencia_oee or 100.0)) / 100.0
        aproveitamento = 1.0 - (max(0.0, float(self.perda_refugo_pct or 0.0)) / 100.0)
        if aproveitamento <= 0:
            aproveitamento = 0.01
        return round((tempo / postos) / (eficiencia * aproveitamento), 2)

    @property
    def capacidade_hora_pecas(self):
        tc = self.tempo_ciclo_efetivo_segundos
        return round(3600.0 / tc, 1) if tc > 0 else 0.0

    @property
    def capacidade_dia_pecas(self):
        horas = float(self.fluxo.horas_trabalho_dia or 8.8) if self.fluxo else 8.8
        return int(round(self.capacidade_hora_pecas * horas))

