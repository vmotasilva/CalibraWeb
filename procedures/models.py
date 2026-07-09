# -*- coding: utf-8 -*-
"""
Models para o módulo Procedures (Procedimentos, Treinamentos, Fornecedores e Cotações)

Unificação dos módulos:
- training: Procedimentos e Treinamentos
- procurements: Fornecedores e Cotações
"""

from django.db import models
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from decimal import Decimal
from core.models import TURNOS_CHOICES


# ==============================================================================
# PROCEDIMENTOS E TREINAMENTOS
# ==============================================================================

class MatrizProcedimento(models.Model):
    """Matriz funcional para classificação de procedimentos."""
    nome = models.CharField(max_length=120, unique=True, verbose_name="Nome da Matriz")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Matriz de Procedimento"
        verbose_name_plural = "Matrizes de Procedimentos"
        ordering = ["nome"]


class SubAreaProcedimento(models.Model):
    """Sub-área vinculada a uma matriz de procedimentos."""
    matriz = models.ForeignKey(
        MatrizProcedimento,
        on_delete=models.CASCADE,
        related_name="sub_areas",
        verbose_name="Matriz",
    )
    nome = models.CharField(max_length=120, verbose_name="Nome da Sub-Área")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.matriz.nome} - {self.nome}"

    class Meta:
        verbose_name = "Sub-Área de Procedimento"
        verbose_name_plural = "Sub-Áreas de Procedimentos"
        ordering = ["matriz__nome", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["matriz", "nome"],
                name="uniq_subarea_procedimento_por_matriz",
            )
        ]


class ResponsavelTreinamentoMatriz(models.Model):
    """Define o colaborador responsável pelos treinamentos de uma matriz ou sub-área em cada turno."""

    matriz = models.ForeignKey(
        MatrizProcedimento,
        on_delete=models.CASCADE,
        related_name="responsaveis_treinamento",
        verbose_name="Matriz",
    )
    sub_area = models.ForeignKey(
        SubAreaProcedimento,
        on_delete=models.CASCADE,
        related_name="responsaveis_treinamento",
        verbose_name="Sub-Área",
        null=True,
        blank=True,
    )
    turno = models.CharField(
        max_length=20,
        choices=TURNOS_CHOICES,
        verbose_name="Turno",
    )
    colaborador = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.PROTECT,
        related_name="responsabilidades_treinamento",
        verbose_name="Colaborador Responsável",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.sub_area_id and self.sub_area.matriz_id != self.matriz_id:
            from django.core.exceptions import ValidationError

            raise ValidationError({"sub_area": "A sub-área deve pertencer à matriz selecionada."})
        return super().clean()

    def __str__(self):
        escopo = self.sub_area.nome if self.sub_area_id else self.matriz.nome
        return f"{self.matriz.nome} / {escopo} - {self.get_turno_display()}: {self.colaborador.nome_completo}"

    class Meta:
        verbose_name = "Responsável de Treinamento por Matriz/Sub-Área"
        verbose_name_plural = "Responsáveis de Treinamento por Matriz/Sub-Área"
        ordering = ["matriz__nome", "sub_area__nome", "turno"]
        constraints = [
            models.UniqueConstraint(
                fields=["matriz", "turno"],
                condition=models.Q(sub_area__isnull=True),
                name="uniq_resp_trein_matriz_turno_geral",
            ),
            models.UniqueConstraint(
                fields=["matriz", "sub_area", "turno"],
                condition=models.Q(sub_area__isnull=False),
                name="uniq_resp_trein_subarea_turno",
            )
        ]
        indexes = [
            models.Index(fields=["turno"], name="resp_trein_matriz_turno_idx"),
            models.Index(fields=["colaborador"], name="resp_trein_matriz_colab_idx"),
            models.Index(fields=["sub_area"], name="resp_trein_subarea_idx"),
        ]

class Procedimento(models.Model):
    """Documento de procedimento operacional (GED)."""
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código", null=True, blank=True)
    nome = models.CharField(max_length=200, verbose_name="Nome/Título do Documento", null=True, blank=True)
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição/Objetivo/Função")
    pasta = models.CharField(max_length=200, null=True, blank=True, verbose_name="Pasta (Local no Qualiex)")
    classificacao = models.CharField(max_length=100, verbose_name="Classificação (Tipo de Procedimento)", null=True, blank=True)
    autor = models.CharField(max_length=100, verbose_name="Autor (Texto Livre)", null=True, blank=True)
    numero_revisao = models.CharField(max_length=10, verbose_name="Número da Revisão", null=True, blank=True)
    ultima_revisao = models.DateField(null=True, blank=True, verbose_name="Última Revisão")
    data_aprovacao = models.DateField(null=True, blank=True, verbose_name="Data de Aprovação")
    proxima_revisao = models.DateField(null=True, blank=True, verbose_name="Próxima Revisão")
    data_validade = models.DateField(null=True, blank=True, verbose_name="Data de Validade")
    documentos_controlados = models.CharField(max_length=50, null=True, blank=True, verbose_name="Documentos Controlados")
    matriz = models.CharField(max_length=100, null=True, blank=True, verbose_name="Matriz")
    sub_area = models.CharField(max_length=100, null=True, blank=True, verbose_name="Sub-Área")
    area_conhecimento = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name="Área de Conhecimento",
        help_text="Área de conhecimento do procedimento para classificação de treinamentos"
    )
    criticidade = models.CharField(
        max_length=20,
        choices=[
            ('CRITICO', 'Crítico'),
            ('NAO_CRITICO', 'Não Crítico'),
        ],
        null=True, blank=True,
        verbose_name="Criticidade",
        help_text="Nível de criticidade do procedimento"
    )

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    class Meta:
        verbose_name = "Procedimento"
        verbose_name_plural = "Procedimentos (GED)"
        ordering = ["codigo"]
        indexes = [
            models.Index(fields=["criticidade"], name="proc_criticidade_idx"),
            models.Index(fields=["matriz"], name="proc_matriz_idx"),
            models.Index(fields=["sub_area"], name="proc_sub_area_idx"),
        ]


class Area(models.Model):
    """Área macro para classificação de procedimentos."""
    nome = models.CharField(max_length=100, unique=True, verbose_name='Nome da Área')
    descricao = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = 'Área'
        verbose_name_plural = 'Áreas (Macro)'
        ordering = ['nome']


class PacoteTreinamento(models.Model):
    """Pacote que agrupa procedimentos para treinamento."""
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Pacote")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    procedimentos = models.ManyToManyField(
        Procedimento, verbose_name="Procedimentos Incluídos", related_name="pacotes"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Pacote de Treinamento"
        verbose_name_plural = "Pacotes de Treinamento"


class ProcedimentoRevisao(models.Model):
    """Histórico de revisões de procedimentos."""
    procedimento = models.ForeignKey(Procedimento, on_delete=models.CASCADE, related_name='historico_revisoes')
    revisao = models.CharField(max_length=10)
    data_revisao = models.DateField(null=True, blank=True)
    data_aprovacao = models.DateField(null=True, blank=True)
    elaborador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='revisoes_elaboradas')
    revisor = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='revisoes_revisadas')
    aprovador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='revisoes_aprovadas')
    arquivo_prev = models.FileField(upload_to='procedimentos/rev/', null=True, blank=True, verbose_name='Arquivo Revisão Anterior')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de Revisão de Procedimento'
        verbose_name_plural = 'Histórico de Revisões'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.procedimento.codigo} Rev {self.revisao}"


# ==============================================================================
# TREINAMENTOS
# ==============================================================================

class ListaPresenca(models.Model):
    """Lista de presença que agrupa múltiplos treinamentos realizados na mesma sessão."""
    codigo = models.CharField(max_length=50, unique=True, editable=False, verbose_name="Código")
    titulo = models.CharField(max_length=200, verbose_name="Título da Sessão")
    
    # Instrutor: Flexível (nome livre + FK opcional)
    instrutor_nome = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name="Nome do Instrutor (Texto Livre)",
        help_text="Digite o nome do instrutor. Será vinculado automaticamente se encontrado na base."
    )
    instrutor = models.ForeignKey(
        'rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, 
        related_name="listas_presenca_como_instrutor", verbose_name="Instrutor (Base de Dados)"
    )
    
    data_sessao = models.DateField(verbose_name="Data da Sessão")
    hora_inicio = models.TimeField(null=True, blank=True, verbose_name="Hora Início")
    hora_fim = models.TimeField(null=True, blank=True, verbose_name="Hora Fim")
    carga_horaria = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Carga Horária (h)")
    local = models.CharField(max_length=200, null=True, blank=True, verbose_name="Local")
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")
    
    # Template de lista de presença (layout/estrutura)
    template = models.ForeignKey(
        'TemplateListaPresenca', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="listas_presenca", verbose_name="Template de Layout",
        help_text="Template Excel que define o layout e colunas dessa lista de presença"
    )
    
    # Evidência documental: Arquivo assinado
    arquivo_assinado = models.FileField(
        upload_to='listas_presenca_assinadas/', null=True, blank=True,
        verbose_name="Arquivo Assinado (PDF/Imagem)",
        help_text="Upload da lista de presença assinada pelos participantes"
    )
    data_upload_assinado = models.DateTimeField(null=True, blank=True, verbose_name="Data do Upload")
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="listas_presenca_criadas"
    )

    def save(self, *args, **kwargs):
        if not self.codigo:
            # Gerar código: LP + ano + número sequencial
            from django.db.models import Max
            import datetime
            ano_atual = datetime.datetime.now().year
            ultimo = ListaPresenca.objects.filter(
                codigo__startswith=f'LP{ano_atual}'
            ).aggregate(Max('codigo'))['codigo__max']
            
            if ultimo:
                try:
                    ultimo_num = int(ultimo.replace(f'LP{ano_atual}-', ''))
                    novo_num = ultimo_num + 1
                except ValueError:
                    novo_num = 1
            else:
                novo_num = 1
            
            self.codigo = f'LP{ano_atual}-{novo_num:04d}'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"

    @property
    def colaboradores_unicos(self):
        """Retorna queryset dos colaboradores únicos nesta lista."""
        return self.registros.filter(
            colaborador__isnull=False
        ).values_list('colaborador', flat=True).distinct()
    
    @property
    def procedimentos_unicos(self):
        """Retorna queryset dos procedimentos únicos nesta lista."""
        return self.registros.filter(
            procedimento__isnull=False
        ).values_list('procedimento', flat=True).distinct()

    class Meta:
        verbose_name = "Lista de Presença"
        verbose_name_plural = "Listas de Presença"
        ordering = ["-data_sessao", "-codigo"]


class ParticipanteExterno(models.Model):
    """Participante externo (não cadastrado como colaborador) em treinamentos/reuniões."""
    nome_completo = models.CharField(max_length=200, verbose_name="Nome Completo")
    cpf = models.CharField(max_length=14, null=True, blank=True, verbose_name="CPF")
    empresa = models.CharField(max_length=200, null=True, blank=True, verbose_name="Empresa/Instituição")
    email = models.EmailField(null=True, blank=True, verbose_name="E-mail")
    telefone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefone")
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.empresa:
            return f"{self.nome_completo} ({self.empresa})"
        return self.nome_completo

    class Meta:
        verbose_name = "Participante Externo"
        verbose_name_plural = "Participantes Externos"
        ordering = ["nome_completo"]


class RegistroTreinamento(models.Model):
    """Registro de treinamento/reunião para colaboradores ou externos."""
    TIPO_CHOICES = [
        ('PROCEDIMENTO', 'Treinamento em Procedimento'),
        ('ALINHAMENTO', 'Alinhamento Interno'),
        ('REUNIAO', 'Reunião'),
        ('CAPACITACAO', 'Capacitação/Curso'),
        ('OUTRO', 'Outro'),
    ]
    
    # Participante: Flexível (nome livre + FK opcional)
    colaborador_nome = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name="Nome do Colaborador (Texto Livre)",
        help_text="Digite o nome do colaborador. Será vinculado automaticamente se encontrado na base."
    )
    colaborador = models.ForeignKey(
        'rh.Colaborador', on_delete=models.SET_NULL, related_name="treinamentos",
        null=True, blank=True, verbose_name="Colaborador (Base de Dados)"
    )
    participante_externo = models.ForeignKey(
        ParticipanteExterno, on_delete=models.CASCADE, related_name="treinamentos",
        null=True, blank=True, verbose_name="Participante Externo"
    )
    
    # Tipo e conteúdo (pode ser procedimento OU outro tipo)
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, default='PROCEDIMENTO',
        verbose_name="Tipo"
    )
    procedimento = models.ForeignKey(
        Procedimento, on_delete=models.CASCADE, related_name="registros_treinamento",
        null=True, blank=True, verbose_name="Procedimento"
    )
    titulo_treinamento = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name="Título do Treinamento/Reunião",
        help_text="Obrigatório quando não há procedimento vinculado"
    )
    descricao = models.TextField(
        null=True, blank=True,
        verbose_name="Descrição/Conteúdo"
    )
    
    lista_presenca = models.ForeignKey(
        ListaPresenca, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registros", verbose_name="Lista de Presença"
    )
    revisor_qualidade = models.ForeignKey(
        'rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name="revisoes_qualidade"
    )
    revisao_treinada = models.CharField(max_length=10, null=True, blank=True, default='01')
    data_treinamento = models.DateField(null=True, blank=True)  # Null = ainda não treinado
    validade_treinamento = models.DateField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    
    # Campos adicionais para importação detalhada
    categoria_comunicacao = models.CharField(
        max_length=100, null=True, blank=True,
        verbose_name="Categoria - Forma de Comunicação"
    )
    metodologia_treinamento = models.CharField(
        max_length=100, null=True, blank=True,
        verbose_name="Metodologia de Treinamento"
    )
    area_conhecimento = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name="Área de Conhecimento"
    )
    facilitador_fornecedor = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name="Nome do Facilitador ou Fornecedor"
    )
    carga_horaria = models.CharField(
        max_length=10, null=True, blank=True,
        verbose_name="Carga Horária (hh:mm)"
    )
    custo_treinamento = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Custo do Treinamento (R$ por pessoa)"
    )
    data_final_treinamento = models.DateField(
        null=True, blank=True,
        verbose_name="Data Final do Treinamento"
    )
    mes_referencia = models.CharField(
        max_length=20, null=True, blank=True,
        verbose_name="Mês de Referência"
    )
    necessita_avaliacao_eficacia = models.BooleanField(
        default=False,
        verbose_name="Necessidade de Avaliação de Eficácia"
    )
    data_limite_avaliacao_eficacia = models.DateField(
        null=True, blank=True,
        verbose_name="Data Limite para Avaliação de Eficácia"
    )
    resultado_avaliacao = models.TextField(
        null=True, blank=True,
        verbose_name="Resultado da Avaliação"
    )
    avaliacao_eficacia_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDENTE', 'Pendente'),
            ('EFICAZ', 'Eficaz'),
            ('INEFICAZ', 'Ineficaz'),
            ('NAO_APLICA', 'Não se Aplica'),
        ],
        null=True, blank=True,
        verbose_name="Status da Avaliação de Eficácia",
        help_text="Status da avaliação de eficácia para procedimentos críticos"
    )
    avaliacao_eficacia_data = models.DateField(
        null=True, blank=True,
        verbose_name="Data da Avaliação de Eficácia"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Define se o grupo/sub-grupo se aplica ao colaborador"
    )
    
    def clean(self):
        """Validação customizada."""
        from django.core.exceptions import ValidationError
        
        # Deve ter colaborador OU externo, não ambos
        if self.colaborador and self.participante_externo:
            raise ValidationError('Não pode ter colaborador e participante externo ao mesmo tempo.')
        if not self.colaborador and not self.participante_externo:
            raise ValidationError('Deve ter colaborador ou participante externo.')
        
        # Se tipo for PROCEDIMENTO, deve ter procedimento
        if self.tipo == 'PROCEDIMENTO' and not self.procedimento:
            raise ValidationError('Tipo PROCEDIMENTO requer procedimento vinculado.')
        
        # Se não tem procedimento, deve ter título
        if not self.procedimento and not self.titulo_treinamento:
            raise ValidationError('Treinamentos sem procedimento devem ter título.')
    
    def save(self, *args, **kwargs):
        self.clean()
        if self.procedimento and self.procedimento.criticidade == 'CRITICO':
            self.necessita_avaliacao_eficacia = True
            if self.data_treinamento:
                import datetime
                self.data_limite_avaliacao_eficacia = self.data_treinamento + datetime.timedelta(days=30)
            if not self.avaliacao_eficacia_status:
                self.avaliacao_eficacia_status = 'PENDENTE'
        super().save(*args, **kwargs)
    
    @property
    def participante_nome(self):
        """Retorna nome do participante (colaborador ou externo)."""
        if self.colaborador:
            return self.colaborador.nome
        elif self.participante_externo:
            return self.participante_externo.nome_completo
        return "-"
    
    @property
    def assunto(self):
        """Retorna o assunto do treinamento (procedimento ou título)."""
        if self.procedimento:
            return f"{self.procedimento.codigo} - {self.procedimento.nome}"
        return self.titulo_treinamento or "-"

    @property
    def status_treinamento(self):
        """
        Status: OK, PENDENTE ou NAO_INICIADO
        Se não há data de treinamento: NAO_INICIADO
        Se há data de treinamento: compara com a data de aprovação do documento
        """
        if not self.data_treinamento:
            return "NAO_INICIADO"
            
        if self.procedimento and self.procedimento.data_aprovacao:
            if self.data_treinamento >= self.procedimento.data_aprovacao:
                return "OK"
            else:
                return "PENDENTE"
                
        # Se não tem procedimento ou não tem data de aprovação, mas o treinamento foi realizado, está OK
        return "OK"
    
    def get_status_badge(self):
        """Retorna o HTML do badge de status para usar no template."""
        status = self.status_treinamento
        if status == "OK":
            return '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Em dias</span>'
        else:
            return '<span class="badge bg-danger"><i class="bi bi-exclamation-circle"></i> Pendente</span>'
    
    def get_status_class(self):
        """Retorna apenas a classe CSS para uso em template."""
        if self.status_treinamento == "OK":
            return "badge bg-success"
        elif self.status_treinamento == "PENDENTE":
            return "badge bg-danger"
        else:  # NAO_INICIADO
            return "badge bg-secondary"
    
    def get_status_label(self):
        """Retorna apenas o texto do status."""
        if self.status_treinamento == "OK":
            return "Em dias"
        elif self.status_treinamento == "PENDENTE":
            return "Pendente"
        else:  # NAO_INICIADO
            return "Não iniciado"
    
    def is_ultimo_registro(self):
        """Verifica se é o último registro para este colaborador e procedimento."""
        if not self.procedimento or not self.colaborador:
            return True  # Se não tem ambos, considerar como último
        
        # Encontrar o registro mais recente para esta combinação
        ultimo = RegistroTreinamento.objects.filter(
            colaborador=self.colaborador,
            procedimento=self.procedimento
        ).order_by('-data_treinamento', '-id').first()
        
        return self.id == ultimo.id if ultimo else False

    class Meta:
        verbose_name_plural = "Matriz de Treinamentos"
        # Permitir múltiplos registros do mesmo procedimento em datas diferentes
        unique_together = ("colaborador", "procedimento", "data_treinamento")
        indexes = [
            models.Index(fields=["ativo", "data_treinamento"], name="regtrein_ativo_data_idx"),
            models.Index(fields=["ativo", "colaborador", "procedimento"], name="regtrein_ativo_col_proc_idx"),
        ]


# ==============================================================================
# MATRIZ DE HABILIDADES
# ==============================================================================

class Disciplina(models.Model):
    """Disciplina/habilidade específica a ser avaliada."""
    matriz = models.ForeignKey('MatrizHabilidade', on_delete=models.CASCADE, related_name="disciplinas_matriz", verbose_name="Matriz", null=True, blank=True)
    codigo = models.CharField(max_length=50, editable=False, verbose_name="Código")
    nome = models.CharField(max_length=200, verbose_name="Nome da Disciplina")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    prioridade = models.CharField(max_length=50, null=True, blank=True, verbose_name="Prioridade")
    obrigatoriedade_legal = models.CharField(max_length=100, null=True, blank=True, verbose_name="Obrigatoriedade Legal")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.codigo:
            # Gerar código automático: DISC001, DISC002, etc.
            ultimo = Disciplina.objects.all().order_by('id').last()
            if ultimo:
                try:
                    ultimo_num = int(ultimo.codigo.replace('DISC', ''))
                    self.codigo = f'DISC{str(ultimo_num + 1).zfill(3)}'
                except:
                    self.codigo = 'DISC001'
            else:
                self.codigo = 'DISC001'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    class Meta:
        verbose_name = "Disciplina"
        verbose_name_plural = "Disciplinas"
        ordering = ["codigo"]


class MatrizHabilidade(models.Model):
    """Matriz que agrupa disciplinas por setor/área."""
    codigo = models.CharField(max_length=50, unique=True, editable=False, verbose_name="Código")
    nome = models.CharField(max_length=200, verbose_name="Nome da Matriz")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.codigo:
            # Gerar código automático: MAT001, MAT002, etc.
            ultimo = MatrizHabilidade.objects.all().order_by('id').last()
            if ultimo:
                ultimo_num = int(ultimo.codigo.replace('MAT', ''))
                self.codigo = f'MAT{str(ultimo_num + 1).zfill(3)}'
            else:
                self.codigo = 'MAT001'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    class Meta:
        verbose_name = "Matriz de Habilidade"
        verbose_name_plural = "Matrizes de Habilidades"
        ordering = ["codigo"]


class ColaboradorMatrizHabilidade(models.Model):
    """Associação de colaborador a matriz de habilidade para avaliação."""
    colaborador = models.ForeignKey('rh.Colaborador', on_delete=models.CASCADE, related_name="matrizes_habilidade")
    matriz = models.ForeignKey(MatrizHabilidade, on_delete=models.CASCADE, related_name="colaboradores")
    data_atribuicao = models.DateField(verbose_name="Data de Atribuição", auto_now_add=True)
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.colaborador.nome_completo} - {self.matriz.codigo}"

    class Meta:
        verbose_name = "Colaborador em Matriz de Habilidade"
        verbose_name_plural = "Colaboradores em Matrizes de Habilidade"
        unique_together = ("colaborador", "matriz")
        ordering = ["colaborador__nome_completo"]


class AvaliacaoHabilidade(models.Model):
    """Avaliação de habilidade de colaborador em disciplina específica."""
    NIVEIS = [
        (-1, "N/A - Não se Aplica"),
        (0, "0 - Há Intenção de Treinar"),
        (1, "1 - Colaborador em Treinamento"),
        (2, "2 - Treinado"),
        (3, "3 - Treinado na Plataforma LOFT"),
    ]
    
    colaborador = models.ForeignKey('rh.Colaborador', on_delete=models.CASCADE, related_name="avaliacoes_habilidade")
    disciplina = models.ForeignKey(Disciplina, on_delete=models.CASCADE, related_name="avaliacoes")
    matriz = models.ForeignKey(MatrizHabilidade, on_delete=models.CASCADE, related_name="avaliacoes")
    nivel = models.IntegerField(choices=NIVEIS, default=0, verbose_name="Nível de Competência")
    data_avaliacao = models.DateField(verbose_name="Data da Avaliação")
    avaliador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name="avaliacoes_realizadas", verbose_name="Avaliador")
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.colaborador.nome_completo} - {self.disciplina.nome} (Nível {self.nivel})"

    class Meta:
        verbose_name = "Avaliação de Habilidade"
        verbose_name_plural = "Avaliações de Habilidades"
        unique_together = ("colaborador", "disciplina", "matriz")
        ordering = ["-data_avaliacao"]


class HistoricoAvaliacaoHabilidade(models.Model):
    """Histórico de alterações nas avaliações de habilidade."""
    avaliacao = models.ForeignKey(AvaliacaoHabilidade, on_delete=models.CASCADE, related_name="historico")
    nivel_anterior = models.IntegerField(null=True, blank=True, verbose_name="Nível Anterior")
    nivel_novo = models.IntegerField(verbose_name="Nível Novo")
    avaliador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="historico_avaliacoes", verbose_name="Avaliador")
    data_avaliacao = models.DateField(null=True, blank=True, verbose_name="Data da Avaliação (anterior)")
    data_avaliacao_nova = models.DateField(verbose_name="Data da Avaliação (nova)")
    observacoes_anterior = models.TextField(null=True, blank=True, verbose_name="Observações Anteriores")
    observacoes_nova = models.TextField(null=True, blank=True, verbose_name="Observações Novas")
    alterado_em = models.DateTimeField(auto_now_add=True, verbose_name="Data/Hora da Alteração")
    tipo_alteracao = models.CharField(
        max_length=20,
        choices=[('criacao', 'Criação'), ('atualizacao', 'Atualização')],
        default='atualizacao',
        verbose_name="Tipo de Alteração"
    )

    def __str__(self):
        return f"Histórico - {self.avaliacao.colaborador.nome_completo} ({self.alterado_em.strftime('%d/%m/%Y %H:%M')})"

    class Meta:
        verbose_name = "Histórico de Avaliação de Habilidade"
        verbose_name_plural = "Históricos de Avaliações de Habilidades"
        ordering = ["-alterado_em"]


class SolicitacaoValidacaoMatriz(models.Model):
    """Solicitação para validação de uma matriz de habilidades."""
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('validada', 'Validada'),
        ('rejeitada', 'Rejeitada'),
    ]
    
    matriz = models.ForeignKey(MatrizHabilidade, on_delete=models.CASCADE, related_name="validacoes_solicitadas")
    solicitante = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True, 
                                    related_name="validacoes_solicitadas")
    validador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True,
                                  related_name="validacoes_para_fazer", verbose_name="Designado para Validar")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    motivo_solicitacao = models.TextField(null=True, blank=True)
    motivo_rejeicao = models.TextField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    validado_em = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Validação {self.matriz.nome} - {self.get_status_display()}"
    
    class Meta:
        verbose_name = "Solicitação de Validação de Matriz"
        verbose_name_plural = "Solicitações de Validação de Matrizes"
        ordering = ["-criado_em"]


class HistoricoValidacaoMassa(models.Model):
    """Histórico de validações em massa executadas."""
    matriz = models.ForeignKey(MatrizHabilidade, on_delete=models.CASCADE, related_name="validacoes_massa")
    validador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True,
                                  related_name="validacoes_massa_realizadas")
    total_avaliacoes = models.IntegerField(verbose_name="Total de Avaliações")
    avaliacoes_atualizadas = models.IntegerField(verbose_name="Avaliações Atualizadas")
    motivo = models.TextField(null=True, blank=True)
    executado_em = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Validação Massa {self.matriz.nome} - {self.executado_em.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name = "Histórico de Validação em Massa"
        verbose_name_plural = "Históricos de Validação em Massa"
        ordering = ["-executado_em"]


# ==============================================================================
# PERFIS E GRUPOS DE TREINAMENTO
# ==============================================================================

class PerfilTreinamento(models.Model):
    """Perfil de cargo/função que define treinamentos necessários."""
    codigo = models.CharField(max_length=50, unique=True, editable=False, verbose_name="Código")
    nome = models.CharField(max_length=200, verbose_name="Nome do Perfil")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.codigo:
            # Obter o último código
            ultimo_perfil = PerfilTreinamento.objects.order_by('codigo').last()
            if ultimo_perfil and ultimo_perfil.codigo.startswith('PERF'):
                try:
                    # Extrai o número do último código
                    ultimo_numero = int(ultimo_perfil.codigo.replace('PERF', ''))
                    novo_numero = ultimo_numero + 1
                except ValueError:
                    novo_numero = 1
            else:
                novo_numero = 1
            
            self.codigo = f'PERF{novo_numero:03d}'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    class Meta:
        verbose_name = "Perfil de Treinamento"
        verbose_name_plural = "Perfis de Treinamento"
        ordering = ["codigo"]


class GrupoTreinamento(models.Model):
    """Grupo dentro de um perfil de treinamento."""
    perfil = models.ForeignKey(PerfilTreinamento, on_delete=models.CASCADE, related_name="grupos")
    nome = models.CharField(max_length=200, verbose_name="Nome do Grupo")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    ordem = models.IntegerField(default=0, verbose_name="Ordem de Exibição")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.perfil.nome} > {self.nome}"

    class Meta:
        verbose_name = "Grupo de Treinamento"
        verbose_name_plural = "Grupos de Treinamento"
        ordering = ["perfil", "ordem", "nome"]


class SubGrupoTreinamento(models.Model):
    """Sub-grupo com procedimentos associados."""
    grupo = models.ForeignKey(GrupoTreinamento, on_delete=models.CASCADE, related_name="subgrupos")
    nome = models.CharField(max_length=200, verbose_name="Nome do Sub-Grupo")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    procedimentos = models.ManyToManyField(Procedimento, related_name="subgrupos_treinamento", 
                                          verbose_name="Procedimentos")
    ordem = models.IntegerField(default=0, verbose_name="Ordem de Exibição")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.grupo.perfil.nome} > {self.grupo.nome} > {self.nome}"

    class Meta:
        verbose_name = "Sub-Grupo de Treinamento"
        verbose_name_plural = "Sub-Grupos de Treinamento"
        ordering = ["grupo", "ordem", "nome"]


class ColaboradorPerfil(models.Model):
    """Associação de colaborador com perfis de treinamento."""
    colaborador = models.ForeignKey('rh.Colaborador', on_delete=models.CASCADE, related_name="perfis_treinamento")
    perfil = models.ForeignKey(PerfilTreinamento, on_delete=models.CASCADE, related_name="colaboradores")
    grupos_selecionados = models.JSONField(
        null=True, 
        blank=True, 
        verbose_name="Grupos/Subgrupos Selecionados",
        help_text="Estrutura: {'grupos': [id1, id2], 'subgrupos': [id1, id2]}"
    )
    data_atribuicao = models.DateField(verbose_name="Data de Atribuição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.colaborador.nome_completo} - {self.perfil.nome}"
    
    def get_procedimentos_necessarios(self):
        """Retorna todos os procedimentos que o colaborador precisa treinar."""
        from procedures.models import Procedimento

        selecao = self.grupos_selecionados or {}
        grupos_ids = selecao.get('grupos') or []
        subgrupos_ids = selecao.get('subgrupos') or []

        # Sem seleção específica (ou seleção vazia): retorna todos do perfil
        if not grupos_ids and not subgrupos_ids:
            return Procedimento.objects.filter(
                subgrupos_treinamento__grupo__perfil=self.perfil
            ).distinct()

        # Priorizar seleção por subgrupos (mais específica)
        if subgrupos_ids:
            return Procedimento.objects.filter(
                subgrupos_treinamento__id__in=subgrupos_ids
            ).distinct()

        # Seleção por grupos: inclui procedimentos de todos os subgrupos desses grupos
        return Procedimento.objects.filter(
            subgrupos_treinamento__grupo__perfil=self.perfil,
            subgrupos_treinamento__grupo__id__in=grupos_ids,
        ).distinct()

    def get_subgrupos_status(self):
        """Retorna um dicionário com o status ativo/inativo de cada subgrupo para este colaborador.
        Formato: {'subgrupo_id': 1, 'subgrupo_id2': 0, ...}"""
        import json
        from procedures.models import RegistroTreinamento
        
        resultado = {}
        
        if self.grupos_selecionados and self.grupos_selecionados.get('subgrupos'):
            for subgrupo_id in self.grupos_selecionados['subgrupos']:
                # Verificar se há registros ativos para este subgrupo
                subgrupo = SubGrupoTreinamento.objects.get(id=subgrupo_id)
                procedimentos = subgrupo.procedimentos.all()
                
                # Verificar se todos os registros deste subgrupo estão ativos
                registros = RegistroTreinamento.objects.filter(
                    colaborador=self.colaborador,
                    procedimento__in=procedimentos
                )
                
                if registros.exists():
                    # Se há registros, usar o status do primeiro (devem ser todos iguais)
                    resultado[str(subgrupo_id)] = int(registros.first().ativo)
                else:
                    # Se não há registros, considerar ativo por padrão
                    resultado[str(subgrupo_id)] = 1
        
        return json.dumps(resultado)

    class Meta:
        verbose_name = "Colaborador-Perfil"
        verbose_name_plural = "Colaboradores-Perfis"
        unique_together = ("colaborador", "perfil")
        ordering = ["colaborador", "perfil"]


class PacoteIntegracao(models.Model):
    """Pacote de integração com os procedimentos padrão para um perfil de colaborador."""
    perfil = models.ForeignKey(PerfilTreinamento, on_delete=models.CASCADE, related_name="pacotes_integracao", verbose_name="Perfil de Treinamento")
    nome = models.CharField(max_length=100, verbose_name="Nome do Pacote", default="Integração Geral")
    procedimentos = models.ManyToManyField(Procedimento, verbose_name="Procedimentos de Integração", related_name="pacotes_integracao")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome} ({self.perfil.nome})"

    class Meta:
        verbose_name = "Pacote de Integração"
        verbose_name_plural = "Pacotes de Integração"


# ==============================================================================
# PLANEJAMENTO DE TREINAMENTOS
# ==============================================================================

class DisciplinaProcedimento(models.Model):
    """Associação entre Disciplinas (Matriz de Habilidades) e Procedimentos de Treinamento."""
    disciplina = models.ForeignKey(
        Disciplina, 
        on_delete=models.CASCADE, 
        related_name="procedimentos_associados",
        verbose_name="Disciplina"
    )
    procedimento = models.ForeignKey(
        Procedimento,
        on_delete=models.CASCADE,
        related_name="disciplinas_associadas",
        verbose_name="Procedimento"
    )
    obrigatorio = models.BooleanField(
        default=True,
        verbose_name="Obrigatório",
        help_text="Se o procedimento é obrigatório para esta disciplina"
    )
    ordem = models.IntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="Ordem de execução do procedimento"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.disciplina.nome} → {self.procedimento.codigo}"

    class Meta:
        verbose_name = "Associação Disciplina-Procedimento"
        verbose_name_plural = "Associações Disciplina-Procedimento"
        unique_together = ('disciplina', 'procedimento')
        ordering = ['disciplina', 'ordem']


class PlanejamentoTreinamento(models.Model):
    """Planejamento de treinamento futuro com 3 tipos de origem."""
    
    # Tipos de origem
    ORIGEM_CHOICES = [
        ("DEMANDA", "Demanda Existente"),
        ("MATRIZ", "Matriz de Habilidades"),
        ("LIVRE", "Planejamento Livre"),
        ("INTEGRACAO", "Integração"),
    ]
    
    STATUS_CHOICES = [
        ("PLANEJADO", "Planejado"),
        ("CONFIRMADO", "Confirmado"),
        ("REALIZADO", "Realizado"),
        ("CANCELADO", "Cancelado"),
        ("ATRASADO", "Atrasado"),
    ]
    
    # Identificação
    titulo = models.CharField(max_length=200, verbose_name="Título do Treinamento")
    origem = models.CharField(
        max_length=20,
        choices=ORIGEM_CHOICES,
        default="LIVRE",
        verbose_name="Origem/Tipo de Planejamento"
    )
    
    # Ligações com origem
    procedimentos = models.ManyToManyField(
        Procedimento,
        related_name="planejamentos",
        verbose_name="Procedimentos",
        blank=True,
        help_text="Procedimentos incluídos neste planejamento"
    )
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planejamentos",
        verbose_name="Disciplina",
        help_text="Preenchido automaticamente quando origem é MATRIZ"
    )
    
    # Participantes
    colaboradores = models.ManyToManyField(
        'rh.Colaborador',
        related_name="treinamentos_planejados", 
        verbose_name="Colaboradores"
    )
    instrutor = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="treinamentos_ministrados",
        verbose_name="Instrutor"
    )
    
    # Datas e execução
    data_prevista = models.DateField(verbose_name="Data Prevista")
    horario_previsto = models.DateTimeField(null=True, blank=True, verbose_name="Horário Previsto para Começar")
    data_realizada = models.DateField(null=True, blank=True, verbose_name="Data Realizada")
    carga_horaria = models.IntegerField(null=True, blank=True, verbose_name="Carga Horária (minutos)")
    local = models.CharField(max_length=200, null=True, blank=True, verbose_name="Local")
    
    # Status e rastreamento
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PLANEJADO",
        verbose_name="Status"
    )
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")
    
    # Auditoria
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def clean(self):
        """Validar campos obrigatórios conforme origem."""
        from django.core.exceptions import ValidationError
        
        if self.origem == "MATRIZ" and not self.disciplina:
            raise ValidationError("Disciplina é obrigatória quando origem é 'Matriz de Habilidades'")

    def update_status_if_overdue(self):
        """Atualiza o status para ATRASADO se a data prevista passou e não foi realizado."""
        from django.utils import timezone
        today = timezone.now().date()
        
        # Se a data prevista passou, não foi realizado e não está cancelado, marca como atrasado
        if (self.data_prevista < today and 
            self.status not in ["REALIZADO", "CANCELADO", "ATRASADO"]):
            self.status = "ATRASADO"
            self.save(update_fields=['status', 'atualizado_em'])
            return True
        
        return False
    
    def is_overdue(self):
        """Verifica se o planejamento está atrasado."""
        from django.utils import timezone
        today = timezone.now().date()
        return self.data_prevista < today and self.status not in ["REALIZADO", "CANCELADO", "ATRASADO"]

    def __str__(self):
        return f"{self.titulo} - {self.data_prevista} ({self.get_origem_display()})"

    class Meta:
        verbose_name = "Planejamento de Treinamento"
        verbose_name_plural = "Planejamentos de Treinamentos"
        ordering = ["-data_prevista"]


# ==============================================================================
# FORNECEDORES E COTAÇÕES
# ==============================================================================

class Fornecedor(models.Model):
    """Fornecedor homologado ou em análise."""
    STATUS = [
        ("HOMOLOGADO", "Homologado"),
        ("BLOQUEADO", "Bloqueado"),
        ("EM_ANALISE", "Em Análise"),
    ]
    nome_fantasia = models.CharField(max_length=100)
    razao_social = models.CharField(max_length=150, null=True, blank=True)
    cnpj = models.CharField(max_length=20, unique=True)
    contato = models.CharField(max_length=100)
    email = models.EmailField()
    telefone = models.CharField(max_length=20)
    escopo_servico = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default="EM_ANALISE")
    nota_media = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)

    def __str__(self):
        return f"{self.nome_fantasia}"

    class Meta:
        verbose_name_plural = "Fornecedores"


class AvaliacaoFornecedor(models.Model):
    """Avaliação de desempenho de fornecedor."""
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.CASCADE, related_name="avaliacoes"
    )
    data_avaliacao = models.DateField(auto_now_add=True)
    avaliador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True)
    nota_tecnica = models.IntegerField(default=10)
    nota_pontualidade = models.IntegerField(default=10)
    nota_atendimento = models.IntegerField(default=10)
    observacao = models.TextField(null=True, blank=True)

    def media(self):
        """Calcula média das notas."""
        return round(
            (self.nota_tecnica + self.nota_pontualidade + self.nota_atendimento) / 3, 1
        )


class ProcessoCotacao(models.Model):
    """Processo de cotação de instrumentos."""
    STATUS = [("ABERTO", "Aberto"), ("FECHADO", "Fechado"), ("CANCELADO", "Cancelado")]
    titulo = models.CharField(max_length=100)
    data_abertura = models.DateField(auto_now_add=True)
    prazo_limite = models.DateField()
    instrumentos = models.ManyToManyField('metrologia.Instrumento')
    status = models.CharField(max_length=20, choices=STATUS, default="ABERTO")
    responsavel = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.titulo} ({self.status})"

    class Meta:
        verbose_name_plural = "Processos de Cotação"


class Orcamento(models.Model):
    """Orçamento de fornecedor para processo de cotação."""
    processo = models.ForeignKey(
        ProcessoCotacao, on_delete=models.CASCADE, related_name="orcamentos"
    )
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    prazo_execucao_dias = models.IntegerField()
    arquivo_proposta = models.FileField(upload_to="orcamentos/")
    vencedor = models.BooleanField(default=False)
    observacoes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"R$ {self.valor_total} - {self.fornecedor}"


# ==============================================================================
# SIGNALS
# ==============================================================================

@receiver(m2m_changed, sender=PacoteTreinamento.procedimentos.through)
def aplicar_pacotes_treinamento(sender, instance, action, pk_set, **kwargs):
    """Aplica pacotes de treinamento quando procedimentos são adicionados."""
    if action == "post_add":
        pacotes = PacoteTreinamento.objects.filter(pk__in=pk_set)
        for pacote in pacotes:
            for proc in pacote.procedimentos.all():
                if not getattr(proc, "aplica_treinamento", False):
                    continue
                RegistroTreinamento.objects.get_or_create(
                    colaborador=instance,
                    procedimento=proc,
                )


@receiver(post_save, sender=AvaliacaoFornecedor)
def update_fornecedor_score(sender, instance, **kwargs):
    """Atualiza nota média do fornecedor após avaliação."""
    f = instance.fornecedor
    avgs = f.avaliacoes.all()
    if avgs:
        f.nota_media = round(sum([a.media() for a in avgs]) / len(avgs), 1)
    f.save()

class TemplateListaPresenca(models.Model):
    """Template/modelo para geração de listas de presença baseado em PDF com placeholders"""
    
    TIPO_ARQUIVO = [
        ('pdf', 'PDF'),
        ('docx', 'Word (.docx)'),
    ]
    
    nome = models.CharField(max_length=200, verbose_name="Nome do Template")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    tipo_arquivo = models.CharField(max_length=10, choices=TIPO_ARQUIVO, default='pdf', verbose_name="Tipo de Arquivo")
    
    # PDF template com placeholders
    arquivo_pdf_template = models.FileField(
        upload_to='templates_pdf_lista_presenca/',
        null=True, blank=True,
        verbose_name="Arquivo PDF Template",
        help_text="PDF base com placeholders como {{titulo}}, {{data_hora}}, {{facilitador}}, etc."
    )
    
    # Configurações
    tem_pagina_assinatura = models.BooleanField(
        default=True, 
        verbose_name="Tem Página de Assinatura?",
        help_text="Se sim, será adicionada página extra para assinaturas"
    )
    
    num_linhas_assinatura = models.IntegerField(
        default=20,
        verbose_name="Número de Linhas para Assinatura",
        help_text="Quantas linhas de participantes caberão na página de assinatura"
    )
    
    # JSON com informações dos placeholders configurados
    # Estrutura: {"titulo": "Título do Treinamento", "data_hora": "Data e Hora", ...}
    placeholders_mapeados = models.JSONField(
        default=dict, blank=True,
        verbose_name="Placeholders Mapeados",
        help_text="Dicionário com placeholder → label"
    )
    
    mapeamento_completo = models.BooleanField(
        default=False,
        verbose_name="Mapeamento Completo?",
        help_text="Todos os campos obrigatórios foram mapeados?"
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True, verbose_name="Template Ativo?")
    
    def __str__(self):
        return f"{self.nome}"
    
    def get_placeholders_list(self):
        """Retorna lista de placeholders encontrados no mapeamento"""
        return list(self.placeholders_mapeados.keys()) if self.placeholders_mapeados else []
    
    class Meta:
        verbose_name = "Template de Lista de Presença"
        verbose_name_plural = "Templates de Listas de Presença"
        ordering = ["-ativo", "-atualizado_em"]


class MapeamentoCampoListaPresenca(models.Model):
    """Mapeia placeholders do template PDF para campos de dados"""
    
    CAMPOS_DISPONIVEIS = [
        ('titulo', 'Título do Treinamento'),
        ('facilitador', 'Facilitador/Fornecedor'),
        ('data', 'Data'),
        ('hora_inicio', 'Hora de Início'),
        ('hora_fim', 'Hora de Fim'),
        ('carga_horaria', 'Carga Horária'),
        ('local', 'Local'),
        ('procedimentos', 'Procedimentos/Assuntos'),
        ('empresa', 'Empresa'),
        ('departamento', 'Departamento'),
        ('instrutoria', 'Instrutoria'),
        ('observacoes', 'Observações'),
    ]
    
    template = models.ForeignKey(TemplateListaPresenca, on_delete=models.CASCADE, related_name="mapeamentos")
    
    # Placeholder exato no PDF (ex: {{titulo}}, {{data_hora}})
    placeholder = models.CharField(
        max_length=100, default='',
        verbose_name="Placeholder",
        help_text="Placeholder exato encontrado no PDF (ex: {{titulo}})"
    )
    
    # Campo da ListaPresenca que alimentará este placeholder
    campo_dados = models.CharField(
        max_length=50, choices=CAMPOS_DISPONIVEIS, null=True, blank=True,
        verbose_name="Campo de Dados",
        help_text="Qual campo da lista de presença alimentará este placeholder"
    )
    
    # Formato de exibição (ex: "dd/mm/yyyy" para datas)
    formato = models.CharField(
        max_length=100, null=True, blank=True,
        verbose_name="Formato de Exibição",
        help_text="Ex: dd/mm/yyyy para datas, moeda para valores, etc"
    )
    
    obrigatorio = models.BooleanField(
        default=True,
        verbose_name="Campo Obrigatório?",
        help_text="Se deve ser validado se está preenchido"
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.template.nome} - {self.placeholder} → {self.get_campo_dados_display()}"
    
    class Meta:
        verbose_name = "Mapeamento de Placeholder"
        verbose_name_plural = "Mapeamentos de Placeholders"
        ordering = ["placeholder"]
        unique_together = [["template", "placeholder"]]  # Um placeholder por template