from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date, timedelta

# ==============================================================================
# OPÇÕES E CONSTANTES GERAIS
# ==============================================================================
STATUS_CHOICES = [
    ('ATIVO', 'Ativo'),
    ('INATIVO', 'Inativo'),
    ('INSS', 'Afastado INSS')
]

# Atualizado conforme solicitado
TURNOS_CHOICES = [
    ('ADM', 'Administrativo'),
    ('TURNO_1', 'Turno 1'),
    ('TURNO_2', 'Turno 2'),
    ('TURNO_3', 'Turno 3'),
    ('12X36', '12x36') # Mantido como opção extra comum
]

RESULTADO_CALIBRA = [
    ('APROVADO', 'Aprovado'),
    ('COM_RESTricao', 'Aprovado c/ Restrição'),
    ('REPROVADO', 'Reprovado')
]

# ==============================================================================
# 0. ESTRUTURA ORGANIZACIONAL (SETORES E CUSTOS)
# ==============================================================================
class Setor(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Setor")
    # Responsável genérico (texto), a hierarquia real fica em HierarquiaSetor
    responsavel = models.CharField(max_length=100, null=True, blank=True, verbose_name="Responsável Genérico")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "0.1 Cadastro de Setores"
        ordering = ['nome']

class CentroCusto(models.Model):
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name='centros_custo', verbose_name="Setor Pertencente")
    codigo = models.CharField(max_length=20, verbose_name="Código (Ex: 2050)")
    descricao = models.CharField(max_length=100, null=True, blank=True, verbose_name="Descrição (Opcional)")

    def __str__(self):
        return f"{self.codigo} - {self.descricao or self.setor.nome}"

    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "0.2 Centros de Custo"
        unique_together = ('setor', 'codigo')

# ==============================================================================
# 1. GESTÃO DE PESSOAS (RH)
# ==============================================================================
class Colaborador(models.Model):
    # Identificação
    matricula = models.CharField(max_length=20, unique=True, verbose_name="Matrícula")
    username = models.CharField(max_length=50, unique=True, verbose_name="Login (Caixa Alta)")
    
    # Dados Pessoais/Profissionais
    nome_completo = models.CharField(max_length=100, verbose_name="Nome Completo")
    cargo = models.CharField(max_length=100, verbose_name="Cargo/Função")
    grupo = models.CharField(max_length=50, verbose_name="Grupo (Macro)")
    
    # Vínculos
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, verbose_name="Setor")
    centro_custo = models.ForeignKey(CentroCusto, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Centro de Custo")
    turno = models.CharField(max_length=20, choices=TURNOS_CHOICES, default='ADM', verbose_name="Turno")

    # Controle de Acesso
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    is_admin = models.BooleanField(default=False, verbose_name="Administrador")
    password_last_changed = models.DateField(null=True, blank=True, verbose_name="Última Troca de Senha")
    criado_em = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.matricula = self.matricula.upper().strip()
        self.username = self.username.upper().strip()
        self.nome_completo = self.nome_completo.upper().strip()
        self.cargo = self.cargo.upper().strip()
        self.grupo = self.grupo.upper().strip()
        super().save(*args, **kwargs)

    def get_chefia(self):
        """Retorna o objeto de Hierarquia correspondente ao Setor/Turno deste colaborador."""
        if not self.setor: return None
        try:
            return HierarquiaSetor.objects.get(setor=self.setor, turno=self.turno)
        except HierarquiaSetor.DoesNotExist:
            return None

    def __str__(self):
        return self.nome_completo
    
    class Meta:
        verbose_name = "Colaborador"
        verbose_name_plural = "1. Colaboradores (RH)"

class HierarquiaSetor(models.Model):
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, verbose_name="Setor")
    turno = models.CharField(max_length=20, choices=TURNOS_CHOICES, verbose_name="Turno")
    
    # Cadeia de Comando
    lider = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name='liderados_setor', verbose_name="Líder")
    supervisor = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name='supervisionados_setor', verbose_name="Supervisor")
    gerente = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name='gerenciados_setor', verbose_name="Gerente")
    diretor = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name='diretoria_setor', verbose_name="Diretor")

    def __str__(self):
        return f"Hierarquia: {self.setor.nome} - {self.get_turno_display()}"

    class Meta:
        verbose_name = "Definição de Hierarquia"
        verbose_name_plural = "1.1 Hierarquia (Setor x Turno)"
        unique_together = ('setor', 'turno')

# ==============================================================================
# 2. METROLOGIA (INSTRUMENTOS)
# ==============================================================================
class Instrumento(models.Model):
    STATUS_INSTRUMENTO = [('ATIVO', 'Ativo'), ('INATIVO', 'Inativo'), ('SUCATA', 'Sucata')]

    tag = models.CharField(max_length=50, unique=True, verbose_name="Identificação/Tag")
    descricao = models.CharField(max_length=200, verbose_name="Descrição do Equipamento")
    marca = models.CharField(max_length=100, null=True, blank=True, verbose_name="Fabricante")
    modelo = models.CharField(max_length=100, null=True, blank=True, verbose_name="Modelo")
    serie = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nº de Série")
    
    # Localização vinculada ao Setor
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, verbose_name="Setor de Instalação")
    status = models.CharField(max_length=20, choices=STATUS_INSTRUMENTO, default='ATIVO')

    def __str__(self):
        return f"{self.tag} - {self.descricao}"
    
    class Meta:
        verbose_name = "Instrumento"
        verbose_name_plural = "2. Instrumentos (Cadastro Físico)"

class TipoMedicao(models.Model):
    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE, related_name='medicoes', verbose_name="Instrumento")
    grandeza = models.CharField(max_length=100, verbose_name="Grandeza (Ex: Temperatura)")
    faixa = models.CharField(max_length=100, verbose_name="Faixa de Medição", null=True, blank=True)
    resolucao = models.CharField(max_length=100, verbose_name="Resolução", null=True, blank=True)
    
    # Controle de Vencimento
    periodicidade_meses = models.IntegerField(default=12, verbose_name="Freq. (Meses)")
    data_ultima_calibracao = models.DateField(null=True, blank=True, verbose_name="Última Calibração")
    data_proxima_calibracao = models.DateField(null=True, blank=True, verbose_name="Vencimento")

    def save(self, *args, **kwargs):
        if self.data_ultima_calibracao and self.periodicidade_meses:
            dias = self.periodicidade_meses * 30
            self.data_proxima_calibracao = self.data_ultima_calibracao + timedelta(days=dias)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.instrumento.tag} | {self.grandeza}"
    
    class Meta:
        verbose_name = "Monitoramento de Vencimento"
        verbose_name_plural = "3. Painel de Vencimentos (Tipos de Medição)"
        unique_together = ('instrumento', 'grandeza')

class HistoricoCalibracao(models.Model):
    tipo_medicao = models.ForeignKey(TipoMedicao, on_delete=models.CASCADE, related_name='historico', verbose_name="Tipo de Medição")
    data_calibracao = models.DateField(verbose_name="Data da Calibração")
    certificado_pdf = models.FileField(upload_to='certificados/', verbose_name="Certificado (PDF)", null=True, blank=True)
    resultado = models.CharField(max_length=20, choices=RESULTADO_CALIBRA, default='APROVADO')
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")
    responsavel = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Responsável Validação")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Histórico"
        verbose_name_plural = "4. Histórico de Calibrações"
        ordering = ['-data_calibracao']

@receiver(post_save, sender=HistoricoCalibracao)
def atualizar_datas_instrumento(sender, instance, created, **kwargs):
    if created:
        medicao = instance.tipo_medicao
        if not medicao.data_ultima_calibracao or instance.data_calibracao > medicao.data_ultima_calibracao:
            medicao.data_ultima_calibracao = instance.data_calibracao
            medicao.save()

# ==============================================================================
# 5. SUPRIMENTOS (FORNECEDORES E COTAÇÕES)
# ==============================================================================
class Fornecedor(models.Model):
    STATUS_HOMOLOGACAO = [('HOMOLOGADO', 'Homologado'), ('BLOQUEADO', 'Bloqueado'), ('EM_ANALISE', 'Em Análise')]
    
    nome_fantasia = models.CharField(max_length=100, verbose_name="Nome Fantasia")
    razao_social = models.CharField(max_length=150, verbose_name="Razão Social", null=True, blank=True)
    cnpj = models.CharField(max_length=20, unique=True, verbose_name="CNPJ")
    contato = models.CharField(max_length=100, verbose_name="Nome do Contato")
    email = models.EmailField(verbose_name="E-mail")
    telefone = models.CharField(max_length=20, verbose_name="Telefone")
    escopo_servico = models.TextField(verbose_name="Escopo de Serviço")
    status = models.CharField(max_length=20, choices=STATUS_HOMOLOGACAO, default='EM_ANALISE')
    nota_media = models.DecimalField(max_digits=3, decimal_places=1, default=0.0, verbose_name="Nota Média (0-10)")

    def __str__(self):
        return f"{self.nome_fantasia} (Nota: {self.nota_media})"
    
    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "5. Fornecedores"

class AvaliacaoFornecedor(models.Model):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name='avaliacoes')
    data_avaliacao = models.DateField(auto_now_add=True)
    avaliador = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True)
    nota_tecnica = models.IntegerField(verbose_name="Capacidade Técnica (0-10)", default=10)
    nota_pontualidade = models.IntegerField(verbose_name="Pontualidade (0-10)", default=10)
    nota_atendimento = models.IntegerField(verbose_name="Atendimento (0-10)", default=10)
    observacao = models.TextField(null=True, blank=True, verbose_name="Ocorrências/Obs")
    
    def media_final(self):
        return round((self.nota_tecnica + self.nota_pontualidade + self.nota_atendimento) / 3, 1)

    class Meta:
        verbose_name = "Avaliação"
        verbose_name_plural = "Avaliações de Fornecedores"

@receiver(post_save, sender=AvaliacaoFornecedor)
def atualizar_nota_fornecedor(sender, instance, **kwargs):
    fornecedor = instance.fornecedor
    avaliacoes = fornecedor.avaliacoes.all()
    if avaliacoes:
        soma = sum([a.media_final() for a in avaliacoes])
        fornecedor.nota_media = round(soma / len(avaliacoes), 1)
        fornecedor.save()

class ProcessoCotacao(models.Model):
    STATUS_PROCESSO = [('ABERTO', 'Cotação Aberta'), ('FECHADO', 'Finalizado/Aprovado'), ('CANCELADO', 'Cancelado')]
    
    titulo = models.CharField(max_length=100, verbose_name="Título")
    data_abertura = models.DateField(auto_now_add=True)
    prazo_limite = models.DateField(verbose_name="Prazo para envio")
    instrumentos = models.ManyToManyField(Instrumento, verbose_name="Instrumentos do Lote")
    status = models.CharField(max_length=20, choices=STATUS_PROCESSO, default='ABERTO')
    responsavel = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.titulo} ({self.status})"
    
    class Meta:
        verbose_name = "Processo de Cotação"
        verbose_name_plural = "6. Processos de Cotação"

class Orcamento(models.Model):
    processo = models.ForeignKey(ProcessoCotacao, on_delete=models.CASCADE, related_name='orcamentos')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Total (R$)")
    prazo_execucao_dias = models.IntegerField(verbose_name="Prazo Execução (Dias)")
    arquivo_proposta = models.FileField(upload_to='orcamentos/', verbose_name="PDF da Proposta")
    vencedor = models.BooleanField(default=False, verbose_name="Vencedor?")
    observacoes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"R$ {self.valor_total} - {self.fornecedor}"

# ==============================================================================
# 7. GESTÃO DE DOCUMENTOS (GED) E TREINAMENTOS
# ==============================================================================
class Documento(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código (Ex: POP-01)")
    titulo = models.CharField(max_length=200, verbose_name="Título do Procedimento")
    revisao_atual = models.CharField(max_length=10, verbose_name="Revisão Atual (Ex: 05)")
    data_revisao = models.DateField(verbose_name="Data da Revisão")
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Setor Aplicável")
    link_externo = models.URLField(null=True, blank=True, verbose_name="Link para Qualiex (Opcional)")
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.codigo = self.codigo.upper().strip()
        self.titulo = self.titulo.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - Rev. {self.revisao_atual}"

    class Meta:
        verbose_name = "Documento (POP/IT)"
        verbose_name_plural = "7.1 Cadastro de Documentos"
        ordering = ['codigo']

class RegistroTreinamento(models.Model):
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name='treinamentos', verbose_name="Colaborador")
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='registros_treinamento', verbose_name="Documento")
    revisao_treinada = models.CharField(max_length=10, verbose_name="Revisão Treinada")
    data_treinamento = models.DateField(verbose_name="Data do Treinamento")
    validade_treinamento = models.DateField(null=True, blank=True, verbose_name="Validade (Opcional)")
    observacoes = models.TextField(null=True, blank=True)

    @property
    def status_treinamento(self):
        if str(self.revisao_treinada).strip() == str(self.documento.revisao_atual).strip():
            return "VIGENTE"
        return "PENDENTE (Atualizar)"

    def __str__(self):
        return f"{self.colaborador} - {self.documento.codigo}"

    class Meta:
        verbose_name = "Registro de Treinamento"
        verbose_name_plural = "7.2 Matriz de Treinamentos"
        unique_together = ('colaborador', 'documento')