from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import models
from django.utils import timezone

from organization.models import Setor


class Turno(models.Model):
    nome = models.CharField(max_length=60, unique=True)
    sigla = models.CharField(max_length=10, unique=True, help_text='Ex.: T1')
    inicio = models.TimeField(null=True, blank=True, help_text='Horário de início. Com início e fim, a cobrança no sino só considera os turnos já iniciados.')
    fim = models.TimeField(null=True, blank=True, help_text='Horário de término. Se for menor que o início, o turno atravessa a meia-noite.')
    ordem = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ('ordem', 'sigla')

    def __str__(self):
        return f'{self.sigla} - {self.nome}'

    def horario(self):
        return f'{self.inicio:%H:%M} – {self.fim:%H:%M}' if self.inicio and self.fim else '—'


class Frequencia(models.Model):
    """Cadastro das frequências de verificação (ex.: Turno, Diário, Semanal, Cada troca de lâmina)."""
    PERIODICIDADES = [
        ('turno', 'A cada turno'),
        ('diaria', 'Diária'),
        ('semanal', 'Semanal'),
        ('quinzenal', 'Quinzenal'),
        ('mensal', 'Mensal'),
        ('trimestral', 'Trimestral'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
        ('evento', 'Sob demanda / por evento'),
    ]
    nome = models.CharField(max_length=120, unique=True)
    periodicidade = models.CharField(max_length=12, choices=PERIODICIDADES, default='evento')
    ordem = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ('ordem', 'nome')
        verbose_name_plural = 'frequências'

    def __str__(self):
        return self.nome


class ListaOpcoes(models.Model):
    """Lista suspensa reutilizável pelos campos (ex.: Realizado / Não realizado / Máq. parada)."""
    nome = models.CharField(max_length=80, unique=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ('nome',)
        verbose_name = 'lista de opções'
        verbose_name_plural = 'listas de opções'

    def __str__(self):
        return self.nome

    def opcoes_resumo(self):
        return ' · '.join(o.valor if o.conforme else f'{o.valor} (desvio)' for o in self.opcoes.all())


class OpcaoLista(models.Model):
    lista = models.ForeignKey(ListaOpcoes, on_delete=models.CASCADE, related_name='opcoes')
    valor = models.CharField(max_length=60)
    conforme = models.BooleanField(default=True, help_text='Desmarque para opções que indicam desvio (ex.: Nok, Não realizado).')
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('ordem', 'id')
        unique_together = ('lista', 'valor')
        verbose_name = 'opção'
        verbose_name_plural = 'opções'

    def __str__(self):
        return self.valor


SEM_GRUPO = 'Sem grupo'


class GrupoPagina(models.Model):
    """Grupo de páginas de um formulário (ex.: Blocagem, Corte). Vale para todas as revisões; a página liga-se pelo nome."""
    formulario = models.ForeignKey('Formulario', on_delete=models.CASCADE, related_name='grupos')
    nome = models.CharField(max_length=80)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('ordem', 'nome')
        unique_together = ('formulario', 'nome')
        verbose_name = 'grupo de páginas'
        verbose_name_plural = 'grupos de páginas'

    def __str__(self):
        return self.nome


class Formulario(models.Model):
    """Formulário de PCP de um setor (ex.: FOR.080 Surfaçagem). A estrutura fica nas revisões."""
    setor = models.ForeignKey(Setor, on_delete=models.PROTECT, related_name='formularios_pcp')
    codigo = models.CharField(max_length=30, unique=True, help_text='Ex.: FOR.080')
    titulo = models.CharField(max_length=150)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ('codigo',)

    def __str__(self):
        return f'{self.codigo} - {self.titulo}'

    @property
    def versao_vigente(self):
        return self.versoes.filter(status=FormularioVersao.VIGENTE).order_by('-criado_em').first()

    def garantir_grupo(self, nome):
        """Cadastra o grupo (no fim da ordem) se ainda não existir e devolve o registro."""
        grupo = self.grupos.filter(nome=nome).first()
        if grupo is None:
            ultimo = self.grupos.order_by('-ordem').values_list('ordem', flat=True).first()
            grupo = GrupoPagina.objects.create(formulario=self, nome=nome, ordem=(ultimo + 1) if ultimo is not None else 0)
        return grupo

    def atribuir_grupo(self, nomes_paginas, grupo):
        """Move as páginas de mesmo nome, em todas as revisões, para o grupo ('' = remover do grupo)."""
        if grupo:
            self.garantir_grupo(grupo)
        return Pagina.objects.filter(versao__formulario=self, nome__in=list(nomes_paginas)).update(grupo=grupo)

    def paginas_equivalentes(self, nomes):
        """Páginas de mesmo nome nas revisões vigente e em rascunho (as obsoletas ficam como histórico)."""
        return Pagina.objects.filter(versao__formulario=self, versao__status__in=[FormularioVersao.VIGENTE, FormularioVersao.RASCUNHO],
                                     nome__in=list(nomes))

    def ordenar_grupos(self, grupos):
        """Reordena um dict {nome_do_grupo: valor} pela ordem cadastrada; 'Sem grupo' sempre por último."""
        ordem = {g.nome: g.ordem for g in self.grupos.all()}
        chaves = sorted(grupos, key=lambda n: (n == SEM_GRUPO, ordem.get(n, 10 ** 6), n.lower()))
        return {k: grupos[k] for k in chaves}


class FormularioVersao(models.Model):
    """Revisão do formulário. Só rascunhos são editáveis; a vigente é travada e uma mudança vira nova revisão."""
    RASCUNHO, VIGENTE, OBSOLETA = 'rascunho', 'vigente', 'obsoleta'
    STATUS = [(RASCUNHO, 'Rascunho'), (VIGENTE, 'Vigente'), (OBSOLETA, 'Obsoleta')]

    formulario = models.ForeignKey(Formulario, on_delete=models.CASCADE, related_name='versoes')
    revisao = models.CharField(max_length=10, help_text='Ex.: R15')
    status = models.CharField(max_length=10, choices=STATUS, default=RASCUNHO)
    vigencia = models.DateField(null=True, blank=True, help_text='Data em que a revisão passou a valer.')
    motivo = models.TextField(blank=True, help_text='O que mudou nesta revisão.')
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ('-criado_em', '-id')
        unique_together = ('formulario', 'revisao')

    def __str__(self):
        return f'{self.formulario.codigo}.{self.revisao}'

    @property
    def editavel(self):
        return self.status == self.RASCUNHO

    def publicar(self):
        """Torna esta revisão a vigente e marca a anterior como obsoleta."""
        FormularioVersao.objects.filter(formulario=self.formulario, status=self.VIGENTE).exclude(pk=self.pk).update(status=self.OBSOLETA)
        self.status = self.VIGENTE
        self.vigencia = self.vigencia or timezone.localdate()
        self.save(update_fields=['status', 'vigencia'])

    def proxima_revisao(self):
        """Sugere o rótulo da próxima revisão (R15 -> R16), preservando o padding."""
        digitos = ''.join(c for c in self.revisao if c.isdigit())
        if not digitos:
            return f'{self.revisao}.1'
        prefixo = self.revisao[:self.revisao.index(digitos)]
        return f'{prefixo}{int(digitos) + 1:0{len(digitos)}d}'

    def clonar(self, revisao, usuario=None, motivo=''):
        """Cria um rascunho com a mesma estrutura (páginas e campos) para a nova revisão."""
        nova = FormularioVersao.objects.create(
            formulario=self.formulario, revisao=revisao, status=self.RASCUNHO, motivo=motivo, criado_por=usuario)
        for pagina in self.paginas.prefetch_related('campos'):
            campos = list(pagina.campos.all())
            pagina.pk = None
            pagina.versao = nova
            pagina.save()
            for campo in campos:
                campo.pk = None
                campo.pagina = pagina
                campo.save()
        return nova


class Pagina(models.Model):
    """Página do formulário: um equipamento/processo com a sua lista de verificações."""
    versao = models.ForeignKey(FormularioVersao, on_delete=models.CASCADE, related_name='paginas')
    nome = models.CharField(max_length=120)
    codigo_sistema = models.CharField(max_length=60, blank=True, help_text='Código da página no sistema (aba da planilha).')
    grupo = models.CharField(max_length=80, blank=True, help_text='Agrupador no índice (ex.: Blocagem, Corte, Polimento).')
    maquina = models.ForeignKey('maquinas.Maquina', null=True, blank=True, on_delete=models.SET_NULL, related_name='paginas_pcp')
    ordem = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ('grupo', 'ordem', 'nome')

    def __str__(self):
        return self.nome


class Campo(models.Model):
    """Item verificado numa página (linha do formulário)."""
    LISTA, NUMERO, TEXTO = 'lista', 'numero', 'texto'
    TIPOS = [(LISTA, 'Lista suspensa'), (NUMERO, 'Número'), (TEXTO, 'Texto')]

    pagina = models.ForeignKey(Pagina, on_delete=models.CASCADE, related_name='campos')
    item = models.CharField(max_length=20, blank=True, help_text='Código do item no formulário (ex.: B-12).')
    etapa = models.CharField('Etapa / contexto', max_length=250, blank=True,
                             help_text='Etapa do processo, receita ou máquina a que o item pertence (agrupa itens na tela).')
    descricao = models.CharField('O que verificar', max_length=300)
    especificacao = models.TextField('Especificação / tolerância', blank=True)
    metodo = models.CharField('Método de verificação', max_length=300, blank=True)
    plano_reacao = models.TextField('Plano de reação', blank=True)
    responsavel = models.CharField('Responsável', max_length=60, blank=True)
    frequencia = models.ForeignKey(Frequencia, null=True, blank=True, on_delete=models.SET_NULL, related_name='campos')
    frequencia_detalhe = models.CharField('Detalhe da frequência', max_length=400, blank=True,
                                          help_text='Texto original da frequência quando ela é mais específica que o cadastro (ex.: "A cada troca de lâmina").')
    tipo = models.CharField(max_length=10, choices=TIPOS, default=LISTA)
    lista = models.ForeignKey(ListaOpcoes, null=True, blank=True, on_delete=models.PROTECT, related_name='campos')
    minimo = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    maximo = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    unidade = models.CharField(max_length=20, blank=True)
    critico = models.BooleanField('Crítico (nível 3)', default=False)
    ordem = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ('ordem', 'id')

    def __str__(self):
        return f'{self.item} {self.descricao}'.strip()

    def avaliar(self, valor):
        """Conformidade do valor lançado: True/False, ou None quando não há critério (texto livre / sem limites)."""
        valor = (valor or '').strip()
        if not valor:
            return None
        if self.tipo == self.LISTA and self.lista_id:
            op = self.lista.opcoes.filter(valor=valor).first()
            return op.conforme if op else None
        if self.tipo == self.NUMERO and (self.minimo is not None or self.maximo is not None):
            try:
                n = Decimal(valor.replace(',', '.'))
            except InvalidOperation:
                return None
            if self.minimo is not None and n < self.minimo:
                return False
            if self.maximo is not None and n > self.maximo:
                return False
            return True
        return None


class Verificacao(models.Model):
    """Preenchimento de uma página numa data e turno."""
    pagina = models.ForeignKey(Pagina, on_delete=models.PROTECT, related_name='verificacoes')
    data = models.DateField()
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name='verificacoes')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-data', 'turno__ordem')
        unique_together = ('pagina', 'data', 'turno')

    def __str__(self):
        return f'{self.pagina} - {self.data:%d/%m/%Y} {self.turno.sigla}'


class Resposta(models.Model):
    verificacao = models.ForeignKey(Verificacao, on_delete=models.CASCADE, related_name='respostas')
    campo = models.ForeignKey(Campo, on_delete=models.PROTECT, related_name='respostas')
    valor = models.CharField(max_length=255, blank=True)
    conforme = models.BooleanField(null=True, blank=True)

    class Meta:
        unique_together = ('verificacao', 'campo')


class Ocorrencia(models.Model):
    """Registro feito durante uma verificação: simples observação ou registro que requer tratativa."""
    OBSERVACAO, TRATATIVA = 'observacao', 'tratativa'
    TIPOS = [(OBSERVACAO, 'Observação'), (TRATATIVA, 'Registro que requer tratativa')]
    ABERTA, TRATADA = 'aberta', 'tratada'

    verificacao = models.ForeignKey(Verificacao, on_delete=models.CASCADE, related_name='ocorrencias')
    campo = models.ForeignKey(Campo, null=True, blank=True, on_delete=models.SET_NULL, related_name='ocorrencias')
    tipo = models.CharField(max_length=10, choices=TIPOS, default=OBSERVACAO)
    descricao = models.TextField()
    status = models.CharField(max_length=10, default=ABERTA)
    tratativa = models.TextField(blank=True)
    tratada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    tratada_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-criado_em',)

    @property
    def pendente(self):
        return self.tipo == self.TRATATIVA and self.status == self.ABERTA
