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

    Os colaboradores se vinculam ao grupo via ``Colaborador.equipe``; o turno de
    cada membro vem do próprio cadastro do colaborador. A configuração por turno
    (líder e efetivo planejado) fica em ``GrupoEquipeTurno``.
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
    """Configuração de um grupo em um turno: responsável/titular, situação (ativo, vago, parado) e efetivo planejado."""

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
