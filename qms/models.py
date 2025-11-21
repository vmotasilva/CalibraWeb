from django.db import models
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import User
from datetime import date, timedelta

# ==============================================================================
# CONSTANTES E OPÇÕES
# ==============================================================================
STATUS_CHOICES = [('ATIVO', 'Ativo'), ('INATIVO', 'Inativo'), ('INSS', 'Afastado INSS')]
TURNOS_CHOICES = [
    ('ADM', 'Administrativo'), 
    ('TURNO_1', 'Turno 1'), 
    ('TURNO_2', 'Turno 2'), 
    ('TURNO_3', 'Turno 3'), 
    ('12X36', '12x36')
]

# ==============================================================================
# MÓDULO 0: ESTRUTURA
# ==============================================================================
class Setor(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Setor")
    responsavel = models.CharField(max_length=100, null=True, blank=True, verbose_name="Responsável Genérico")
    def __str__(self): return self.nome
    class Meta: verbose_name = "Setor"; verbose_name_plural = "0.1 Cadastro de Setores"; ordering = ['nome']

class CentroCusto(models.Model):
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name='centros_custo', verbose_name="Setor Pertencente")
    codigo = models.CharField(max_length=20, verbose_name="Código")
    descricao = models.CharField(max_length=100, null=True, blank=True, verbose_name="Descrição")
    def __str__(self): return f"{self.codigo} - {self.descricao or self.setor.nome}"
    class Meta: verbose_name = "Centro de Custo"; verbose_name_plural = "0.2 Centros de Custo"; unique_together = ('setor', 'codigo')

# ==============================================================================
# MÓDULO 7: DOCUMENTOS (GED)
# ==============================================================================
class Procedimento(models.Model): 
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    titulo = models.CharField(max_length=200, verbose_name="Título")
    revisao_atual = models.CharField(max_length=10, verbose_name="Revisão Atual")
    data_revisao = models.DateField(verbose_name="Data Rev.", null=True, blank=True)
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Setor Aplicável")
    prioridade = models.CharField(max_length=50, null=True, blank=True)
    habilidade_vinculada = models.CharField(max_length=100, null=True, blank=True)
    tem_copia_fisica = models.BooleanField(default=False)
    aplica_treinamento = models.BooleanField(default=False)
    link_externo = models.URLField(null=True, blank=True)

    def save(self, *args, **kwargs):
        self.codigo = self.codigo.upper().strip()
        self.titulo = self.titulo.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.codigo} - {self.titulo}"
    class Meta: verbose_name = "Procedimento"; verbose_name_plural = "7.1 Procedimentos (GED)"; ordering = ['codigo']

class PacoteTreinamento(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Pacote")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    procedimentos = models.ManyToManyField(Procedimento, verbose_name="Procedimentos Incluídos", related_name="pacotes")
    def __str__(self): return self.nome
    class Meta: verbose_name = "Pacote de Treinamento"; verbose_name_plural = "7.3 Pacotes de Treinamento"

# ==============================================================================
# MÓDULO 1: COLABORADORES (RH)
# ==============================================================================
class Colaborador(models.Model):
    user_django = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário de Acesso (Login)")
    matricula = models.CharField(max_length=20, unique=True, verbose_name="Matrícula")
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True, verbose_name="CPF")
    nome_completo = models.CharField(max_length=100, verbose_name="Nome Completo")
    cargo = models.CharField(max_length=100, verbose_name="Cargo/Função")
    grupo = models.CharField(max_length=50, verbose_name="Grupo (Macro)")
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, verbose_name="Setor")
    centro_custo = models.ForeignKey(CentroCusto, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Centro de Custo")
    turno = models.CharField(max_length=20, choices=TURNOS_CHOICES, default='ADM', verbose_name="Turno")
    salario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Salário (R$)")
    em_ferias = models.BooleanField(default=False, verbose_name="Está de Férias?")
    
    pacotes_treinamento = models.ManyToManyField(PacoteTreinamento, blank=True, verbose_name="Pacotes Atribuídos", related_name="colaboradores")
    is_active = models.BooleanField(default=True, verbose_name="Colaborador Ativo (RH)")
    criado_em = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.matricula = self.matricula.upper().strip()
        self.nome_completo = self.nome_completo.upper().strip()
        if self.cpf: self.cpf = self.cpf.replace('.', '').replace('-', '').strip()
        super().save(*args, **kwargs)

    def get_chefia(self):
        if not self.setor: return None
        try: return HierarquiaSetor.objects.get(setor=self.setor, turno=self.turno)
        except HierarquiaSetor.DoesNotExist: return None

    def __str__(self): return f"{self.nome_completo} ({self.matricula})"
    class Meta: verbose_name = "Colaborador"; verbose_name_plural = "1. Colaboradores (RH)"

@receiver(m2m_changed, sender=Colaborador.pacotes_treinamento.through)
def aplicar_pacotes_treinamento(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        pacotes = PacoteTreinamento.objects.filter(pk__in=pk_set)
        for pacote in pacotes:
            for proc in pacote.procedimentos.all():
                RegistroTreinamento.objects.get_or_create(
                    colaborador=instance,
                    procedimento=proc,
                    defaults={'revisao_treinada': 'PENDENTE', 'data_treinamento': date.today()}
                )

class HierarquiaSetor(models.Model):
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, verbose_name="Setor")
    turno = models.CharField(max_length=20, choices=TURNOS_CHOICES, verbose_name="Turno")
    lider = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name='liderados_setor', verbose_name="Líder")
    supervisor = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name='supervisionados_setor', verbose_name="Supervisor")
    gerente = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name='gerenciados_setor', verbose_name="Gerente")
    diretor = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name='diretoria_setor', verbose_name="Diretor")
    def __str__(self): return f"Hierarquia: {self.setor.nome} - {self.get_turno_display()}"
    class Meta: verbose_name = "Hierarquia"; verbose_name_plural = "1.1 Hierarquia (Setor x Turno)"; unique_together = ('setor', 'turno')

class Ferias(models.Model):
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name='historico_ferias')
    data_inicio = models.DateField(verbose_name="Início")
    data_fim = models.DateField(verbose_name="Fim")
    observacao = models.CharField(max_length=200, null=True, blank=True, verbose_name="Obs")
    class Meta: verbose_name = "Férias"; verbose_name_plural = "1.2 Controle de Férias"; ordering = ['-data_inicio']

@receiver(post_save, sender=Ferias)
def atualizar_status_ferias(sender, instance, **kwargs):
    c = instance.colaborador; h = date.today()
    em = c.historico_ferias.filter(data_inicio__lte=h, data_fim__gte=h).exists()
    if c.em_ferias != em: c.em_ferias = em; c.save()

class Ocorrencia(models.Model):
    TIPO = [('FALTA', 'Falta'), ('ATRASO', 'Atraso'), ('ADV', 'Advertência'), ('ELOGIO', 'Elogio'), ('OUTRO', 'Outro')]
    NATUREZA = [('NEGATIVA', '🔴 Negativa'), ('POSITIVA', '🟢 Positiva'), ('NEUTRA', '⚪ Neutra')]
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name='ocorrencias')
    data_ocorrencia = models.DateField(verbose_name="Data"); tipo = models.CharField(max_length=20, choices=TIPO)
    natureza = models.CharField(max_length=10, choices=NATUREZA, default='NEGATIVA')
    titulo = models.CharField(max_length=100, verbose_name="Resumo"); descricao = models.TextField(verbose_name="Detalhes")
    arquivo_evidencia = models.FileField(upload_to='ocorrencias/', null=True, blank=True)
    def save(self, *args, **kwargs):
        if self.tipo in ['FALTA', 'ATRASO', 'ADV']: self.natureza = 'NEGATIVA'
        elif self.tipo == 'ELOGIO': self.natureza = 'POSITIVA'
        super().save(*args, **kwargs)
    class Meta: verbose_name = "Ocorrência"; verbose_name_plural = "1.3 Ocorrências"

class DocumentoPessoal(models.Model):
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name='documentos_pessoais')
    tipo = models.CharField(max_length=50, verbose_name="Tipo")
    arquivo = models.FileField(upload_to='rh_docs/', verbose_name="Arquivo")
    descricao = models.CharField(max_length=100, null=True, blank=True)
    data_upload = models.DateField(auto_now_add=True)
    class Meta: verbose_name = "Documento Pessoal"; verbose_name_plural = "Documentos Pessoais"

# ==============================================================================
# MÓDULO 2: METROLOGIA
# ==============================================================================

class UnidadeMedida(models.Model):
    nome = models.CharField(max_length=50) # Ex: Quilograma
    sigla = models.CharField(max_length=10) # Ex: kg

    def __str__(self):
        return f"{self.nome} ({self.sigla})"
    class Meta: verbose_name_plural = "2.1 Unidades de Medida"

class CategoriaInstrumento(models.Model):
    nome = models.CharField(max_length=100) # Ex: Manômetro
    descricao = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nome
    class Meta: verbose_name_plural = "2.2 Categorias de Instrumentos"

class Instrumento(models.Model):
    tag = models.CharField(max_length=50, unique=True, verbose_name="TAG / Identificação")
    codigo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código Interno")
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    fabricante = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    serie = models.CharField(max_length=100, blank=True, null=True)
    
    categoria = models.ForeignKey(CategoriaInstrumento, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Categoria / Família")
    
    ativo = models.BooleanField(default=True)
    data_ultima_calibracao = models.DateField(blank=True, null=True)
    data_proxima_calibracao = models.DateField(blank=True, null=True)
    frequencia_meses = models.IntegerField(default=12, verbose_name="Frequência (Meses)")
    
    responsavel = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True)
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, blank=True)
    localizacao = models.CharField(max_length=100, blank=True, null=True)

    class Meta: 
        verbose_name = "Instrumento"
        verbose_name_plural = "2. Instrumentos"

    def __str__(self):
        return f"{self.tag} - {self.descricao}"

# FAIXA AGORA LIGADA AO INSTRUMENTO (ESPECÍFICA DELE)
class FaixaMedicao(models.Model):
    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE, related_name='faixas')
    unidade = models.ForeignKey(UnidadeMedida, on_delete=models.PROTECT)
    valor_minimo = models.DecimalField(max_digits=10, decimal_places=4)
    valor_maximo = models.DecimalField(max_digits=10, decimal_places=4)
    resolucao = models.DecimalField(max_digits=10, decimal_places=4, help_text="Menor divisão", null=True, blank=True)
    incerteza_padrao = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)

    def __str__(self):
        return f"{self.valor_minimo} a {self.valor_maximo} {self.unidade.sigla}"
    class Meta: verbose_name_plural = "2.3 Faixas de Medição"

class HistoricoCalibracao(models.Model):
    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE, related_name='historico_calibracoes', verbose_name="Instrumento")
    
    data_calibracao = models.DateField(verbose_name="Data da Calibração")
    data_aprovacao = models.DateField(verbose_name="Data de Aprovação/Validação", default=date.today)
    numero_certificado = models.CharField(max_length=100, verbose_name="N° do Certificado", default="S/N")
    
    proxima_calibracao = models.DateField(null=True, blank=True, verbose_name="Vencimento")
    certificado = models.FileField(upload_to='certificados/', null=True, blank=True, verbose_name="Certificado (PDF)")
    
    RESULTADO_CHOICES = [
        ('APROVADO', 'Aprovado sem correções'),
        ('CONDICIONAL', 'Aprovado com correções'),
        ('REPROVADO', 'Reprovado')
    ]
    resultado = models.CharField(max_length=50, choices=RESULTADO_CHOICES, default='APROVADO', verbose_name="Resultado")
    
    responsavel = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Responsável Interno")
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta: 
        verbose_name = "Histórico de Calibração"
        verbose_name_plural = "4. Histórico de Calibrações"
        ordering = ['-data_calibracao']
        unique_together = ('instrumento', 'data_calibracao', 'data_aprovacao', 'numero_certificado')
    
    def __str__(self):
        return f"{self.instrumento.tag} - {self.data_calibracao}"

# ==============================================================================
# MÓDULO 5: SUPRIMENTOS
# ==============================================================================
class Fornecedor(models.Model):
    STATUS = [('HOMOLOGADO', 'Homologado'), ('BLOQUEADO', 'Bloqueado'), ('EM_ANALISE', 'Em Análise')]
    nome_fantasia = models.CharField(max_length=100); razao_social = models.CharField(max_length=150, null=True, blank=True)
    cnpj = models.CharField(max_length=20, unique=True); contato = models.CharField(max_length=100)
    email = models.EmailField(); telefone = models.CharField(max_length=20); escopo_servico = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default='EM_ANALISE')
    nota_media = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    def __str__(self): return f"{self.nome_fantasia}"
    class Meta: verbose_name_plural = "5. Fornecedores"

class AvaliacaoFornecedor(models.Model):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name='avaliacoes')
    data_avaliacao = models.DateField(auto_now_add=True)
    avaliador = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True)
    nota_tecnica = models.IntegerField(default=10); nota_pontualidade = models.IntegerField(default=10); nota_atendimento = models.IntegerField(default=10)
    observacao = models.TextField(null=True, blank=True)
    def media(self): return round((self.nota_tecnica + self.nota_pontualidade + self.nota_atendimento) / 3, 1)
    @receiver(post_save, sender=AvaliacaoFornecedor)
    def update_fornecedor_score(sender, instance, **kwargs):
        f = instance.fornecedor
        avgs = f.avaliacoes.all()
        if avgs:
            f.nota_media = round(sum([a.media() for a in avgs]) / len(avgs), 1)
        f.save()

class ProcessoCotacao(models.Model):
    STATUS = [('ABERTO', 'Aberto'), ('FECHADO', 'Fechado'), ('CANCELADO', 'Cancelado')]
    titulo = models.CharField(max_length=100); data_abertura = models.DateField(auto_now_add=True); prazo_limite = models.DateField()
    instrumentos = models.ManyToManyField(Instrumento); status = models.CharField(max_length=20, choices=STATUS, default='ABERTO')
    responsavel = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True)
    def __str__(self): return f"{self.titulo} ({self.status})"
    class Meta: verbose_name_plural = "6. Processos de Cotação"

class Orcamento(models.Model):
    processo = models.ForeignKey(ProcessoCotacao, on_delete=models.CASCADE, related_name='orcamentos')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2); prazo_execucao_dias = models.IntegerField()
    arquivo_proposta = models.FileField(upload_to='orcamentos/'); vencedor = models.BooleanField(default=False); observacoes = models.TextField(null=True, blank=True)
    def __str__(self): return f"R$ {self.valor_total} - {self.fornecedor}"

class RegistroTreinamento(models.Model):
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name='treinamentos')
    procedimento = models.ForeignKey(Procedimento, on_delete=models.CASCADE, related_name='registros_treinamento')
    revisao_treinada = models.CharField(max_length=10); data_treinamento = models.DateField()
    validade_treinamento = models.DateField(null=True, blank=True); observacoes = models.TextField(null=True, blank=True)
    @property
    def status_treinamento(self): 
        if str(self.revisao_treinada).strip() == str(self.procedimento.revisao_atual).strip(): return "VIGENTE"
        return "PENDENTE"
    class Meta: verbose_name_plural = "7.2 Matriz de Treinamentos"; unique_together = ('colaborador', 'procedimento')

    @receiver([post_save, models.signals.post_delete], sender=HistoricoCalibracao)
    def atualizar_datas_instrumento(sender, instance, **kwargs):
    inst = instance.instrumento
    
    # Busca a calibração mais recente deste instrumento
    ultima_calib = inst.historico_calibracoes.order_by('-data_calibracao').first()
    
    if ultima_calib:
        inst.data_ultima_calibracao = ultima_calib.data_calibracao
        inst.data_proxima_calibracao = ultima_calib.proxima_calibracao
        
        # Atualiza status baseado no resultado do último certificado
        if ultima_calib.resultado == 'REPROVADO':
            inst.ativo = False # Ou criar um status 'MANUTENCAO' se preferir
        else:
            inst.ativo = True
    else:
        # Se apagou todos os históricos, limpa as datas
        inst.data_ultima_calibracao = None
        inst.data_proxima_calibracao = None
    
    inst.save()