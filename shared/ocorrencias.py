"""Central de Ocorrências: visão única das ocorrências de todos os módulos.

Cada origem (Auditoria, Laboratório, PCP, Metrologia) tem um adaptador que sabe:
  - quais ocorrências o usuário pode ver (mesmas regras de acesso das telas de origem);
  - quais envolvem o usuário (responsável, autor ou destinatário);
  - quais ações pode executar sem sair da central.

As ações reaproveitam os mesmos campos/regras das views de origem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from django.core.cache import cache
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from shared.inbox import _can, invalidar_cache_inbox
from shared.permissions import has_view_access

COUNTS_CACHE_KEY = "ocorrencias_counts:v1:user:{uid}"
STATUS_ABERTA = "aberta"
STATUS_ENCERRADA = "encerrada"


@dataclass
class Acao:
    key: str
    label: str
    icon: str
    btn: str = "outline-primary"
    campo: str = ""          # "" (sem formulário) | "texto" | "texto_destinatarios" | "responsavel"
    placeholder: str = ""
    obrigatorio: bool = True


@dataclass
class OcorrenciaItem:
    uid: str                  # "<origem>:<pk>"
    origem: str
    origem_nome: str
    icon: str
    titulo: str
    descricao: str
    status: str               # STATUS_ABERTA | STATUS_ENCERRADA
    data: Any                 # date/datetime de abertura
    envolve_usuario: bool = False
    papel: str = ""           # "Responsável", "Autor", "Destinatário"...
    responsaveis: list[str] = field(default_factory=list)
    prazo: Optional[date] = None
    vencida: bool = False
    detalhes: list[tuple[str, str]] = field(default_factory=list)
    historico: list[tuple[str, str, str]] = field(default_factory=list)  # (quando, quem, texto)
    url_origem: str = ""
    acoes: list[Acao] = field(default_factory=list)

    @property
    def data_ordem(self) -> datetime:
        d = self.data
        if isinstance(d, datetime):
            return timezone.make_aware(d) if timezone.is_naive(d) else d
        if isinstance(d, date):
            return timezone.make_aware(datetime(d.year, d.month, d.day))
        return timezone.now()


def _nome_user(u) -> str:
    if not u:
        return ""
    return (u.get_full_name() or u.get_username()).strip()


def _fmt_dt(dt) -> str:
    if not dt:
        return ""
    if isinstance(dt, datetime):
        return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M")
    return dt.strftime("%d/%m/%Y")


class ResultadoAcao:
    def __init__(self, ok: bool, msg: str):
        self.ok, self.msg = ok, msg


# ---------------------------------------------------------------------------
# Adaptadores
# ---------------------------------------------------------------------------
class _Origem:
    key = ""
    nome = ""
    icon = "bi-exclamation-diamond"

    def base_qs(self, user):  # todas as ocorrências visíveis ao usuário
        raise NotImplementedError

    def aberta_q(self) -> Q:
        raise NotImplementedError

    def mine_q(self, user) -> Q:
        raise NotImplementedError

    def to_item(self, obj, user, mine_ids: set[int]) -> OcorrenciaItem:
        raise NotImplementedError

    def executar(self, user, obj, acao: str, dados: dict) -> ResultadoAcao:
        raise NotImplementedError

    def pode(self, user, *view_names: str) -> bool:
        try:
            return all(has_view_access(user, vn) for vn in view_names)
        except Exception:
            return False


class OrigemAuditoria(_Origem):
    key, nome, icon = "auditoria", "Auditoria", "bi-clipboard-check"

    def base_qs(self, user):
        from auditoria.models import ComentarioRespostaAuditoria, ModeloAuditoria
        from auditoria.views import _filter_modelos_para_usuario
        from shared.permissions import has_module_access

        if not has_module_access(user, "auditoria"):
            return ComentarioRespostaAuditoria.objects.none()
        modelos = _filter_modelos_para_usuario(user, ModeloAuditoria.objects.all())
        return (
            ComentarioRespostaAuditoria.objects.filter(
                Q(pergunta__modelo__in=modelos) | Q(responsaveis__user_django=user),
                requer_tratativa=True,
                unificada_em__isnull=True,
            )
            .distinct()
            .select_related("pergunta", "pergunta__modelo", "autor", "resolvido_por")
            .prefetch_related("responsaveis")
        )

    def aberta_q(self):
        return Q(status="ABERTA")

    def mine_q(self, user):
        return Q(responsaveis__user_django=user) | Q(autor=user)

    def to_item(self, oc, user, mine_ids):
        hoje = timezone.localdate()
        aberta = oc.status == "ABERTA"
        resp_users = [r.user_django_id for r in oc.responsaveis.all()]
        papel = ""
        if user.pk in resp_users:
            papel = "Responsável"
        elif oc.autor_id == user.pk:
            papel = "Autor"
        detalhes = []
        if oc.acao:
            detalhes.append(("Ação a realizar", oc.acao))
        historico = []
        if oc.resolucao:
            historico.append((_fmt_dt(oc.resolvido_em), _nome_user(oc.resolvido_por), oc.resolucao))
        acoes = []
        if aberta:
            acoes.append(Acao("resolver", "Resolver", "bi-check2-circle", "success", "texto",
                              "Descreva como a ocorrência foi resolvida", obrigatorio=False))
        else:
            acoes.append(Acao("reabrir", "Reabrir", "bi-arrow-counterclockwise", "outline-secondary"))
        return OcorrenciaItem(
            uid=f"{self.key}:{oc.pk}", origem=self.key, origem_nome=self.nome, icon=self.icon,
            titulo=f"{oc.pergunta.modelo.nome} — {oc.pergunta.pergunta[:90]}",
            descricao=(oc.texto or "").strip(),
            status=STATUS_ABERTA if aberta else STATUS_ENCERRADA,
            data=oc.criado_em, envolve_usuario=papel != "", papel=papel,
            responsaveis=[r.nome_completo for r in oc.responsaveis.all()],
            prazo=oc.prazo, vencida=bool(aberta and oc.prazo and oc.prazo < hoje),
            detalhes=detalhes, historico=historico,
            url_origem=reverse("auditoria:modulo") + "#ocorrencias-em-aberto", acoes=acoes,
        )

    def executar(self, user, oc, acao, dados):
        from auditoria.models import ComentarioRespostaAuditoria as C

        if acao == "resolver":
            resolucao = (dados.get("texto") or "").strip()
            if len(resolucao) > 8000:
                return ResultadoAcao(False, "Descrição da resolução muito longa (máx. 8000 caracteres).")
            oc.status, oc.resolucao = C.STATUS_RESOLVIDA, resolucao
            oc.resolvido_em, oc.resolvido_por = timezone.now(), user
            oc.save(update_fields=["status", "resolucao", "resolvido_em", "resolvido_por", "atualizado_em"])
            return ResultadoAcao(True, "Ocorrência de auditoria marcada como resolvida.")
        if acao == "reabrir":
            oc.status, oc.resolvido_em, oc.resolvido_por = C.STATUS_ABERTA, None, None
            oc.save(update_fields=["status", "resolvido_em", "resolvido_por", "atualizado_em"])
            return ResultadoAcao(True, "Ocorrência de auditoria reaberta.")
        return ResultadoAcao(False, "Ação inválida.")


class OrigemLaboratorio(_Origem):
    key, nome, icon = "laboratorio", "Laboratório", "bi-droplet-half"

    def base_qs(self, user):
        from laboratorio.models import OcorrenciaLaboratorio

        if not _can(user, "laboratorio", "laboratorio:ocorrencias_list"):
            return OcorrenciaLaboratorio.objects.none()
        return OcorrenciaLaboratorio.objects.select_related(
            "categoria", "responsavel", "criado_por", "maquina", "colaborador"
        ).prefetch_related("anotacoes_registradas__usuario")

    def aberta_q(self):
        return Q(data_encerramento__isnull=True)

    def mine_q(self, user):
        return Q(responsavel=user) | Q(criado_por=user)

    def _pode_encerrar(self, user, oc) -> bool:
        from shared.permissions import user_has_nav_perm

        return bool(
            user_has_nav_perm(user, "core.nav_laboratorio_encerrar_qualquer_ocorrencia")
            or oc.criado_por_id == user.pk
        ) and self.pode(user, "laboratorio:ocorrencia_close")

    def to_item(self, oc, user, mine_ids):
        aberta = oc.data_encerramento is None
        papel = ""
        if oc.responsavel_id == user.pk:
            papel = "Responsável"
        elif oc.criado_por_id == user.pk:
            papel = "Autor"
        detalhes = [("Impacto", oc.get_impacto_display())]
        if oc.maquina_id:
            detalhes.append(("Máquina", str(oc.maquina)))
        if oc.colaborador_id:
            detalhes.append(("Colaborador", str(oc.colaborador)))
        if oc.consequencias:
            detalhes.append(("Consequências", oc.consequencias))
        if not aberta and oc.observacoes_encerramento:
            detalhes.append(("Encerramento", oc.observacoes_encerramento))
        historico = [
            (_fmt_dt(a.criado_em), a.autor_display, a.texto) for a in oc.anotacoes_registradas.all()[:20]
        ]
        acoes = []
        if self.pode(user, "laboratorio:ocorrencia_notes"):
            acoes.append(Acao("anotar", "Anotar", "bi-journal-text", "outline-primary", "texto",
                              "Registre uma anotação de acompanhamento"))
        if aberta and self._pode_encerrar(user, oc):
            acoes.append(Acao("encerrar", "Encerrar", "bi-check2-circle", "success", "texto",
                              "Impacto final, tratativa adotada e pendências remanescentes", obrigatorio=False))
        return OcorrenciaItem(
            uid=f"{self.key}:{oc.pk}", origem=self.key, origem_nome=self.nome, icon=self.icon,
            titulo=oc.assunto, descricao=(oc.detalhamento or "").strip(),
            status=STATUS_ABERTA if aberta else STATUS_ENCERRADA,
            data=oc.data_abertura, envolve_usuario=papel != "", papel=papel,
            responsaveis=[_nome_user(oc.responsavel)] if oc.responsavel_id else [],
            detalhes=detalhes, historico=historico,
            url_origem=reverse("laboratorio:ocorrencia_detail", args=[oc.pk]), acoes=acoes,
        )

    def executar(self, user, oc, acao, dados):
        from laboratorio.models import OcorrenciaLaboratorioAnotacao

        texto = (dados.get("texto") or "").strip()
        if acao == "anotar":
            if not self.pode(user, "laboratorio:ocorrencia_notes"):
                return ResultadoAcao(False, "Você não tem permissão para registrar anotações.")
            if not texto:
                return ResultadoAcao(False, "Escreva a anotação antes de salvar.")
            OcorrenciaLaboratorioAnotacao.objects.create(ocorrencia=oc, usuario=user, texto=texto)
            return ResultadoAcao(True, f"Anotação registrada em '{oc.assunto}'.")
        if acao == "encerrar":
            if not self._pode_encerrar(user, oc):
                return ResultadoAcao(
                    False, "Apenas quem criou a ocorrência ou um usuário com permissão especial pode encerrá-la."
                )
            if oc.data_encerramento:
                return ResultadoAcao(False, "A ocorrência já está encerrada.")
            agora = timezone.now()
            oc.data_encerramento = max(agora, oc.data_abertura + timedelta(seconds=1))
            if texto:
                oc.observacoes_encerramento = texto
            oc.save()
            return ResultadoAcao(True, f"Ocorrência '{oc.assunto}' encerrada.")
        return ResultadoAcao(False, "Ação inválida.")


class OrigemPcp(_Origem):
    key, nome, icon = "pcp", "PCP", "bi-gear-wide-connected"

    def base_qs(self, user):
        from pcp.models import Ocorrencia

        if not _can(user, "pcp", "pcp:ocorrencias"):
            return Ocorrencia.objects.none()
        return Ocorrencia.objects.filter(tipo=Ocorrencia.TRATATIVA).select_related(
            "verificacao__pagina", "verificacao__turno", "campo", "criado_por", "tratada_por"
        )

    def aberta_q(self):
        return Q(status="aberta")

    def mine_q(self, user):
        return Q(criado_por=user)

    def to_item(self, oc, user, mine_ids):
        aberta = oc.status == "aberta"
        pagina = getattr(getattr(oc.verificacao, "pagina", None), "nome", "") or "Verificação"
        campo = oc.campo.descricao if oc.campo_id else ""
        historico = []
        if oc.tratativa:
            historico.append((_fmt_dt(oc.tratada_em), _nome_user(oc.tratada_por), oc.tratativa))
        acoes = []
        if aberta and self.pode(user, "pcp:ocorrencia_tratar"):
            acoes.append(Acao("tratar", "Registrar tratativa", "bi-check2-circle", "success", "texto",
                              "Descreva a tratativa realizada"))
        papel = "Autor" if oc.criado_por_id == user.pk else ""
        return OcorrenciaItem(
            uid=f"{self.key}:{oc.pk}", origem=self.key, origem_nome=self.nome, icon=self.icon,
            titulo=f"{pagina}" + (f" — {campo}" if campo else ""),
            descricao=(oc.descricao or "").strip(),
            status=STATUS_ABERTA if aberta else STATUS_ENCERRADA,
            data=oc.criado_em, envolve_usuario=papel != "", papel=papel,
            responsaveis=[_nome_user(oc.criado_por)] if oc.criado_por_id else [],
            historico=historico, url_origem=reverse("pcp:ocorrencias"), acoes=acoes,
        )

    def executar(self, user, oc, acao, dados):
        if acao != "tratar":
            return ResultadoAcao(False, "Ação inválida.")
        if not self.pode(user, "pcp:ocorrencia_tratar"):
            return ResultadoAcao(False, "Você não tem permissão para registrar tratativas.")
        texto = (dados.get("texto") or "").strip()
        if not texto:
            return ResultadoAcao(False, "Descreva a tratativa realizada.")
        oc.tratativa, oc.status = texto, "tratada"
        oc.tratada_por, oc.tratada_em = user, timezone.now()
        oc.save()
        return ResultadoAcao(True, "Tratativa registrada.")


class OrigemMetrologia(_Origem):
    key, nome, icon = "metrologia", "Metrologia", "bi-tools"

    def base_qs(self, user):
        from qms.models import OcorrenciaInstrumento

        if not _can(user, "metrologia", "metrologia:relatorio_ocorrencias"):
            return OcorrenciaInstrumento.objects.none()
        return OcorrenciaInstrumento.objects.select_related(
            "instrumento", "instrumento__setor", "usuario_responsavel"
        ).prefetch_related("mensagens__autor", "mensagens__destinatarios")

    def aberta_q(self):
        return Q(status="ABERTA")

    def mine_q(self, user):
        return Q(usuario_responsavel=user) | Q(mensagens__destinatarios=user)

    def to_item(self, oc, user, mine_ids):
        aberta = oc.status == "ABERTA"
        inst = oc.instrumento
        tag = (inst.tag or inst.codigo or f"ID {inst.pk}") if inst else "Instrumento"
        setor = f" ({inst.setor.nome})" if inst and getattr(inst, "setor_id", None) else ""
        papel = ""
        if oc.usuario_responsavel_id == user.pk:
            papel = "Responsável"
        elif oc.pk in mine_ids:
            papel = "Destinatário"
        detalhes = []
        if inst and inst.descricao:
            detalhes.append(("Instrumento", inst.descricao))
        if oc.custo_reparo:
            detalhes.append(("Custo de reparo", f"R$ {oc.custo_reparo}"))
        if not aberta and oc.data_encerramento:
            detalhes.append(("Encerrada em", oc.data_encerramento.strftime("%d/%m/%Y")))
        historico = []
        for m in list(oc.mensagens.all())[-20:]:
            dest = ", ".join(_nome_user(d) for d in m.destinatarios.all())
            txt = m.texto + (f"  → {dest}" if dest else "")
            historico.append((_fmt_dt(m.criado_em), _nome_user(m.autor), txt))
        historico.reverse()
        acoes = []
        if self.pode(user, "metrologia:adicionar_mensagem_ocorrencia"):
            acoes.append(Acao("mensagem", "Mensagem", "bi-chat-left-text", "outline-primary",
                              "texto_destinatarios", "Escreva a mensagem de tratativa"))
        if self.pode(user, "metrologia:atribuir_responsavel_ocorrencia"):
            acoes.append(Acao("atribuir", "Atribuir", "bi-person-check", "outline-secondary", "responsavel",
                              obrigatorio=False))
        if aberta and self.pode(user, "metrologia:encerrar_ocorrencia"):
            acoes.append(Acao("encerrar", "Encerrar", "bi-check2-circle", "success"))
        if not aberta and self.pode(user, "metrologia:reabrir_ocorrencia"):
            acoes.append(Acao("reabrir", "Reabrir", "bi-arrow-counterclockwise", "outline-secondary"))
        return OcorrenciaItem(
            uid=f"{self.key}:{oc.pk}", origem=self.key, origem_nome=self.nome, icon=self.icon,
            titulo=f"{oc.get_tipo_display()}: {tag}{setor}", descricao=(oc.descricao or "").strip(),
            status=STATUS_ABERTA if aberta else STATUS_ENCERRADA,
            data=oc.data_ocorrencia, envolve_usuario=papel != "", papel=papel,
            responsaveis=[_nome_user(oc.usuario_responsavel)] if oc.usuario_responsavel_id else [],
            detalhes=detalhes, historico=historico,
            url_origem=reverse("metrologia:relatorio_ocorrencias") + f"?ocorrencia_id={oc.pk}", acoes=acoes,
        )

    def executar(self, user, oc, acao, dados):
        from django.contrib.auth.models import User
        from qms.models import OcorrenciaMensagem

        antigo = oc.usuario_responsavel
        if acao == "mensagem":
            if not self.pode(user, "metrologia:adicionar_mensagem_ocorrencia"):
                return ResultadoAcao(False, "Você não tem permissão para lançar mensagens.")
            texto = (dados.get("texto") or "").strip()
            if not texto:
                return ResultadoAcao(False, "Escreva a mensagem antes de enviar.")
            ids = [i for i in dados.get("destinatarios", []) if str(i).isdigit()]
            dests = list(User.objects.filter(pk__in=ids, is_active=True))
            msg = OcorrenciaMensagem.objects.create(ocorrencia=oc, autor=user, texto=texto)
            msg.destinatarios.set(dests)
            if dests and not oc.usuario_responsavel_id:
                oc.usuario_responsavel = dests[0]
                oc.save(update_fields=["usuario_responsavel"])
            for u in dests:
                invalidar_cache_inbox(u)
                invalidar_counts(u)
            return ResultadoAcao(True, f"Mensagem lançada na ocorrência #{oc.pk}.")
        if acao == "atribuir":
            if not self.pode(user, "metrologia:atribuir_responsavel_ocorrencia"):
                return ResultadoAcao(False, "Você não tem permissão para atribuir responsável.")
            rid = str(dados.get("responsavel") or "")
            novo = User.objects.filter(pk=rid, is_active=True).first() if rid.isdigit() else None
            if rid and not novo:
                return ResultadoAcao(False, "Usuário selecionado não encontrado.")
            oc.usuario_responsavel = novo
            oc.save(update_fields=["usuario_responsavel"])
            for u in (novo, antigo):
                if u:
                    invalidar_cache_inbox(u)
                    invalidar_counts(u)
            return ResultadoAcao(True, f"Tratativa da ocorrência #{oc.pk} direcionada para {_nome_user(novo)}."
                                 if novo else f"Responsável da ocorrência #{oc.pk} removido.")
        if acao == "encerrar":
            if not self.pode(user, "metrologia:encerrar_ocorrencia"):
                return ResultadoAcao(False, "Você não tem permissão para encerrar ocorrências.")
            oc.status, oc.data_encerramento = "ENCERRADA", timezone.localdate()
            oc.save()
            if antigo:
                invalidar_cache_inbox(antigo)
                invalidar_counts(antigo)
            return ResultadoAcao(True, f"Ocorrência #{oc.pk} encerrada.")
        if acao == "reabrir":
            if not self.pode(user, "metrologia:reabrir_ocorrencia"):
                return ResultadoAcao(False, "Você não tem permissão para reabrir ocorrências.")
            oc.status, oc.data_encerramento = "ABERTA", None
            oc.save()
            if antigo:
                invalidar_cache_inbox(antigo)
                invalidar_counts(antigo)
            return ResultadoAcao(True, f"Ocorrência #{oc.pk} reaberta.")
        return ResultadoAcao(False, "Ação inválida.")


ORIGENS: dict[str, _Origem] = {o.key: o for o in (
    OrigemAuditoria(), OrigemLaboratorio(), OrigemPcp(), OrigemMetrologia(),
)}


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def invalidar_counts(user=None) -> None:
    """Descarta o cache do badge do menu (um usuário, ou todos quando suportado)."""
    try:
        if user is not None:
            cache.delete(COUNTS_CACHE_KEY.format(uid=getattr(user, "pk", user)))
        elif hasattr(cache, "delete_pattern"):
            cache.delete_pattern("ocorrencias_counts:*")
    except Exception:
        pass


def contar_ocorrencias(user: Any) -> dict[str, int]:
    """{'minhas': n, 'abertas': m} — usado no ícone do menu (cache curto por usuário)."""
    vazio = {"minhas": 0, "abertas": 0}
    if not getattr(user, "is_authenticated", False):
        return vazio
    chave = COUNTS_CACHE_KEY.format(uid=user.pk)
    cached = cache.get(chave)
    if isinstance(cached, dict):
        return cached
    minhas = abertas = 0
    for origem in ORIGENS.values():
        try:
            qs = origem.base_qs(user).filter(origem.aberta_q())
            abertas += qs.distinct().count()
            minhas += qs.filter(origem.mine_q(user)).distinct().count()
        except Exception:
            continue
    dados = {"minhas": minhas, "abertas": abertas}
    cache.set(chave, dados, timeout=60)
    return dados


def listar_ocorrencias(user: Any, status: str = "abertas", origem: str = "") -> list[OcorrenciaItem]:
    """Ocorrências visíveis ao usuário, as que o envolvem primeiro (depois vencidas, depois as mais antigas)."""
    itens: list[OcorrenciaItem] = []
    for key, orig in ORIGENS.items():
        if origem and origem != key:
            continue
        try:
            qs = orig.base_qs(user)
            qs = qs.filter(orig.aberta_q()) if status != "encerradas" else qs.exclude(orig.aberta_q())
            mine_ids = set(qs.filter(orig.mine_q(user)).values_list("pk", flat=True))
            for obj in qs.order_by("-pk")[:300]:
                item = orig.to_item(obj, user, mine_ids)
                item.envolve_usuario = item.envolve_usuario or obj.pk in mine_ids
                if item.envolve_usuario and not item.papel:
                    item.papel = "Envolvido"
                itens.append(item)
        except Exception:
            continue
    sinal = -1 if status == "encerradas" else 1  # abertas: mais antigas primeiro; encerradas: mais recentes
    itens.sort(key=lambda i: (not i.envolve_usuario, not i.vencida, sinal * i.data_ordem.timestamp()))
    return itens


def executar_acao(user: Any, uid: str, acao: str, dados: dict) -> ResultadoAcao:
    """Executa uma ação sobre a ocorrência `uid` ("origem:pk"), revalidando o acesso do usuário."""
    key, _, pk = (uid or "").partition(":")
    orig = ORIGENS.get(key)
    if not orig or not pk.isdigit():
        return ResultadoAcao(False, "Ocorrência inválida.")
    obj = orig.base_qs(user).filter(pk=int(pk)).first()
    if obj is None:
        return ResultadoAcao(False, "Ocorrência não encontrada ou sem acesso.")
    res = orig.executar(user, obj, acao, dados)
    if res.ok:
        invalidar_counts()
        invalidar_counts(user)
        invalidar_cache_inbox(user)
    return res
