from django.db import models
from core.models import STATUS_CHOICES, TURNOS_CHOICES

# ==============================================================================
# ORGANIZATION - ESTRUTURA ORGANIZACIONAL
# ==============================================================================

class Unidade(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome da Unidade / Empresa")
    codigo = models.CharField(max_length=50, blank=True, default="", verbose_name="Código / Sigla")
    cnpj = models.CharField(max_length=20, blank=True, default="", verbose_name="CNPJ")
    cidade = models.CharField(max_length=100, blank=True, default="", verbose_name="Cidade")
    estado = models.CharField(max_length=2, blank=True, default="", verbose_name="UF")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Unidade / Empresa"
        verbose_name_plural = "Unidades / Empresas"
        ordering = ["nome"]


class Setor(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Setor")
    responsavel = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Responsável Genérico"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Cadastro de Setores"
        ordering = ["nome"]


class CentroCusto(models.Model):
    setor = models.ForeignKey(
        Setor,
        on_delete=models.CASCADE,
        related_name="centros_custo",
        verbose_name="Setor Pertencente",
    )
    codigo = models.CharField(max_length=20, verbose_name="Código")
    descricao = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Descrição"
    )

    def __str__(self):
        return f"{self.codigo} - {self.descricao or self.setor.nome}"

    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "Centros de Custo"
        unique_together = ("setor", "codigo")


class HierarquiaSetor(models.Model):
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, verbose_name="Setor")
    turno = models.CharField(
        max_length=20, choices=TURNOS_CHOICES, verbose_name="Turno"
    )
    lider = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liderados_setor",
        verbose_name="Líder",
    )
    supervisor = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervisionados_setor",
        verbose_name="Supervisor",
    )
    gerente = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gerenciados_setor",
        verbose_name="Gerente",
    )
    diretor = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diretoria_setor",
        verbose_name="Diretor",
    )

    def __str__(self):
        return f"Hierarquia: {self.setor.nome} - {self.get_turno_display()}"

    class Meta:
        verbose_name = "Hierarquia"
        verbose_name_plural = "Hierarquia (Setor x Turno)"
        unique_together = ("setor", "turno")


class GrupoEquipe(models.Model):
    """Estrutura de trabalho: Setor > Bloco (nível 1) > Posto de trabalho (nível 2).

    Quem ocupa cada posto, por turno, é dado por ``AlocacaoPosto`` (colaboradores, vagas e reservas).
    """

    nome = models.CharField(max_length=100, verbose_name="Nome do Grupo")
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subgrupos",
        verbose_name="Bloco (para postos de trabalho)",
    )
    setor = models.ForeignKey(
        Setor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grupos_equipe",
        verbose_name="Setor",
    )
    descricao = models.CharField(max_length=255, blank=True, default="", verbose_name="Descrição")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.caminho

    @property
    def caminho(self):
        """Nome completo na árvore, ex.: 'Produção › Coating › Linha 1'."""
        nomes, atual, visto = [], self, set()
        while atual is not None and atual.pk not in visto:
            visto.add(atual.pk)
            nomes.append(atual.nome)
            atual = atual.parent
        return " › ".join(reversed(nomes))

    def ids_descendentes(self):
        """IDs de todos os subgrupos (não inclui o próprio grupo)."""
        todos = {}
        for gid, pid in GrupoEquipe.objects.values_list("id", "parent_id"):
            todos.setdefault(pid, []).append(gid)
        resultado, fila = [], list(todos.get(self.pk, []))
        while fila:
            gid = fila.pop()
            if gid in resultado:
                continue
            resultado.append(gid)
            fila.extend(todos.get(gid, []))
        return resultado

    @property
    def nivel(self):
        """1 = Bloco (dentro de um Setor); 2 = Posto de trabalho (dentro de um Bloco)."""
        return 2 if self.parent_id else 1

    @property
    def tipo_label(self):
        return "Posto de trabalho" if self.parent_id else "Bloco"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError("Um grupo não pode ficar dentro dele mesmo.")
            if self.parent.parent_id:
                raise ValidationError("Um posto de trabalho só pode ficar dentro de um bloco (não de outro posto).")
            if self.pk and self.subgrupos.exists():
                raise ValidationError("Este bloco possui postos de trabalho e não pode virar posto de outro bloco.")
        elif not self.setor_id:
            raise ValidationError("Informe o setor do bloco.")

    def save(self, *args, **kwargs):
        if self.parent_id:  # o posto sempre herda o setor do bloco
            self.setor_id = self.parent.setor_id
        super().save(*args, **kwargs)
        if not self.parent_id:
            self.subgrupos.exclude(setor_id=self.setor_id).update(setor_id=self.setor_id)

    class Meta:
        verbose_name = "Grupo de Equipe"
        verbose_name_plural = "Estrutura de Equipes (Grupos)"
        ordering = ["ordem", "nome"]
        unique_together = ("parent", "nome")


class GrupoEquipeTurno(models.Model):
    """OBSOLETO: substituído por ``AlocacaoPosto`` (lista livre de colaboradores, vagas e reservas por turno).

    Mantido apenas para não quebrar a versão anterior durante o deploy; não é mais lido nem gravado.
    """

    grupo = models.ForeignKey(
        GrupoEquipe, on_delete=models.CASCADE, related_name="turnos_config", verbose_name="Grupo"
    )
    turno = models.CharField(max_length=20, choices=TURNOS_CHOICES, verbose_name="Turno")
    SITUACAO_CHOICES = [
        ("ATIVO", "Ativo (com titular)"),
        ("VAGO", "Vago (necessário contratar)"),
        ("RESERVA", "Reserva (equipamento reserva instalado)"),
        ("PARADO", "Parado"),
    ]
    responsavel = models.ForeignKey(
        "rh.Colaborador",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grupos_equipe_responsavel",
        verbose_name="Responsável / Titular do Turno",
    )
    situacao = models.CharField(
        max_length=10, choices=SITUACAO_CHOICES, default="VAGO", verbose_name="Situação"
    )
    efetivo_planejado = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Efetivo Planejado"
    )

    def __str__(self):
        return f"{self.grupo.nome} - {self.get_turno_display()}"

    class Meta:
        verbose_name = "Configuração de Grupo por Turno"
        verbose_name_plural = "Configurações de Grupo por Turno"
        unique_together = ("grupo", "turno")


class AlocacaoPosto(models.Model):
    """O que ocupa um posto de trabalho em um turno: um colaborador, uma VAGA (necessário
    contratar) ou uma RESERVA (equipamento reserva instalado, para quando um falhar).

    Um posto pode ter várias alocações no mesmo turno e o mesmo colaborador pode estar em vários postos.
    """

    TIPO_CHOICES = [
        ("PESSOA", "Colaborador"),
        ("VAGO", "Vago (necessário contratar)"),
        ("RESERVA", "Reserva (equipamento reserva instalado)"),
    ]

    posto = models.ForeignKey(
        GrupoEquipe, on_delete=models.CASCADE, related_name="alocacoes", verbose_name="Posto de trabalho"
    )
    turno = models.CharField(max_length=20, choices=TURNOS_CHOICES, verbose_name="Turno")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="PESSOA", verbose_name="Tipo")
    colaborador = models.ForeignKey(
        "rh.Colaborador",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alocacoes_posto",
        verbose_name="Colaborador",
    )
    observacao = models.CharField(max_length=255, blank=True, default="", verbose_name="Observação")
    criado_em = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.posto.parent_id:
            raise ValidationError("Colaboradores, vagas e reservas são alocados em um posto de trabalho (dentro de um bloco).")
        if self.tipo == "PESSOA" and not self.colaborador_id:
            raise ValidationError("Informe o colaborador.")
        if self.tipo != "PESSOA" and self.colaborador_id:
            raise ValidationError("Vaga e reserva não têm colaborador.")

    def __str__(self):
        quem = self.colaborador.nome_completo if self.colaborador_id else self.get_tipo_display()
        return f"{self.posto.nome} / {self.get_turno_display()}: {quem}"

    class Meta:
        verbose_name = "Alocação em Posto"
        verbose_name_plural = "Alocações em Postos"
        ordering = ["turno", "tipo", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["posto", "turno", "colaborador"],
                condition=models.Q(colaborador__isnull=False),
                name="uniq_alocacao_pessoa_posto_turno",
            )
        ]
