from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Fornecedor(models.Model):
    TIPO_CHOICES = [
        ("CRITICO", "Crítico"),
        ("NAO_CRITICO", "Não Crítico"),
        ("TERCEIRIZADO", "Terceirizado"),
    ]
    empresa = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255)
    endereco = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=18, blank=True, null=True)
    siret = models.CharField(max_length=20, blank=True, null=True)
    ein = models.CharField(max_length=20, blank=True, null=True)
    telefone = models.CharField(max_length=30, blank=True, null=True)
    uf = models.CharField(max_length=2)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="NAO_CRITICO")
    ativo = models.BooleanField(default=True)
    
    def __str__(self):
        return self.empresa

class CategoriaDocumento(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    def __str__(self):
        return self.nome

class DocumentoFornecedor(models.Model):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name="documentos")
    categoria = models.ForeignKey(CategoriaDocumento, on_delete=models.SET_NULL, null=True)
    arquivo = models.FileField(upload_to="documentos_fornecedores/")
    data_validade = models.DateField(blank=True, null=True)
    observacao = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.fornecedor} - {self.categoria}"

class AvaliacaoFornecedor(models.Model):
    TIPO_CHOICES = [
        ("SELECAO", "Seleção"),
        ("REAVALIACAO", "Reavaliação"),
        ("MONITORAMENTO", "Monitoramento"),
    ]
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name="avaliacoes")
    data = models.DateField()
    avaliador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    nota_fiscal = models.CharField(max_length=50, blank=True, null=True)
    tipo_nota = models.CharField(max_length=20, choices=[("PRODUTO", "Produto"), ("SERVICO", "Serviço")], blank=True, null=True)
    pontuacao_ano = models.FloatField(default=100)
    resultado = models.CharField(max_length=20, blank=True)
    observacao = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.fornecedor} - {self.tipo} - {self.data}"

class PerguntaAvaliacao(models.Model):
    TIPO_CHOICES = [
        ("SELECAO", "Seleção"),
        ("REAVALIACAO", "Reavaliação"),
        ("MONITORAMENTO", "Monitoramento"),
    ]
    PRODUTO_SERVICO_CHOICES = [
        ("PRODUTO", "Produto"),
        ("SERVICO", "Serviço"),
        ("AMBOS", "Ambos"),
    ]
    texto = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    produto_servico = models.CharField(
        max_length=10,
        choices=PRODUTO_SERVICO_CHOICES,
        blank=True,
        null=True,
        help_text="Obrigatório para perguntas de Monitoramento"
    )
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.texto} ({self.tipo})" + (f" - {self.get_produto_servico_display()}" if self.produto_servico else "")

class RespostaAvaliacao(models.Model):
    avaliacao = models.ForeignKey(AvaliacaoFornecedor, on_delete=models.CASCADE, related_name="respostas")
    pergunta = models.ForeignKey(PerguntaAvaliacao, on_delete=models.CASCADE)
    resposta = models.BooleanField()  # True=Sim, False=Não
    observacao = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.avaliacao} - {self.pergunta}"

class OcorrenciaNota(models.Model):
    avaliacao = models.ForeignKey(AvaliacaoFornecedor, on_delete=models.CASCADE, related_name="ocorrencias")
    descricao = models.CharField(max_length=255)
    pontuacao_perdida = models.FloatField(default=0.5)
    
    def __str__(self):
        return f"{self.avaliacao} - {self.descricao}"
