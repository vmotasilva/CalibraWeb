"""E-mails da Auditoria Livre para o auditado (plano de ação / CAPA).

O envio nunca levanta exceção para quem chamou: devolve contagens, para a ação principal
(gerar link, aprovar, rejeitar) não falhar por causa de um problema de e-mail.
"""
import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.utils.html import escape, linebreaks

logger = logging.getLogger(__name__)

MAX_DESTINATARIOS = 20


def parse_emails(texto):
    """Separa por vírgula, ponto e vírgula ou quebra de linha. Retorna (válidos, inválidos), sem repetição."""
    if isinstance(texto, (list, tuple)):
        texto = "\n".join(str(t) for t in texto)
    validos, invalidos, vistos = [], [], set()
    for bruto in re.split(r"[,;\s]+", str(texto or "")):
        email = bruto.strip().strip("<>").lower()
        if not email or email in vistos:
            continue
        vistos.add(email)
        try:
            validate_email(email)
            validos.append(email)
        except ValidationError:
            invalidos.append(bruto.strip())
    return validos, invalidos


def _linha(texto):
    """Uma linha só (assunto/cabeçalhos não aceitam quebra de linha)."""
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def _enviar(destinatarios, assunto, texto, html, reply_to=None):
    """Envia uma mensagem por destinatário (ninguém vê o e-mail dos outros). Retorna (enviados, falhas)."""
    enviados = falhas = 0
    for dest in destinatarios[:MAX_DESTINATARIOS]:
        try:
            msg = EmailMultiAlternatives(
                _linha(assunto), texto, settings.DEFAULT_FROM_EMAIL, [dest],
                reply_to=[reply_to] if reply_to else None,
            )
            msg.attach_alternative(html, "text/html")
            msg.send()
            enviados += 1
        except Exception:  # noqa: BLE001 - falha de SMTP não pode derrubar a ação do auditor
            logger.exception("Falha ao enviar e-mail da Auditoria Livre para %s", dest)
            falhas += 1
    return enviados, falhas


def _html(titulo, corpo_html, url=None, rotulo_botao="Abrir plano de ação"):
    botao = (
        f'<p style="margin:24px 0"><a href="{escape(url)}" style="background:#0284c7;color:#fff;'
        f'padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:600">{escape(rotulo_botao)}</a></p>'
        f'<p style="color:#64748b;font-size:12px">Se o botão não abrir, copie este endereço: {escape(url)}</p>'
        if url else ""
    )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:auto;color:#1e293b">'
        f'<h2 style="margin-bottom:4px">{escape(titulo)}</h2>{corpo_html}{botao}'
        '<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">'
        '<p style="color:#94a3b8;font-size:12px">Mensagem automática do Calibra QMS.</p></div>'
    )


def enviar_link_capa(link, url, destinatarios, mensagem="", remetente_nome="", responder_para=""):
    """Envia o link do portal do auditado. Retorna (enviados, falhas)."""
    aud = link.auditoria
    qtd = link.solicitacoes().count()
    validade = f"{link.expira_em:%d/%m/%Y}"
    escopo = f" (tópico: {link.topico})" if link.topico else ""
    de = f" por {remetente_nome}" if remetente_nome else ""
    intro = (
        f"Você foi convidado{de} a responder o plano de ação da auditoria “{aud.titulo}”.\n"
        f"{qtd} item(ns) aguardam a sua resposta{escopo}. O link vale até {validade}."
    )
    extra = f"\n\nMensagem do auditor:\n{mensagem.strip()}" if (mensagem or "").strip() else ""
    texto = f"{intro}{extra}\n\nAcesse: {url}\n\nNão é preciso criar conta ou fazer login."
    corpo = f"<p>{escape(intro).replace(chr(10), '<br>')}</p>"
    if extra:
        corpo += (
            '<blockquote style="border-left:4px solid #cbd5e1;margin:12px 0;padding:4px 14px;color:#475569">'
            f"{linebreaks(escape(mensagem.strip()))}</blockquote>"
        )
    corpo += "<p>Não é preciso criar conta ou fazer login.</p>"
    return _enviar(
        destinatarios, f"Plano de ação pendente: {aud.titulo}", texto,
        _html("Plano de ação pendente", corpo, url), reply_to=responder_para,
    )


def notificar_revisao(sol, decisao, base_url_portal, responder_para=""):
    """Avisa os destinatários dos links (válidos e dentro do escopo do item) sobre a decisão do auditor.

    `base_url_portal(link)` devolve a URL absoluta do portal. Retorna (enviados, falhas, destinatarios_unicos).
    """
    from ..models import CapaLinkLivre

    aud = sol.auditoria
    destinos, url = [], None
    for link in CapaLinkLivre.objects.filter(auditoria=aud, ativo=True):
        if not link.is_valid or not link.lista_emails:
            continue
        if sol.conclusao not in link.conclusoes_alvo() or (link.topico and link.topico != sol.topico):
            continue
        for e in link.lista_emails:
            if e not in destinos:
                destinos.append(e)
        url = url or base_url_portal(link)
    if not destinos:
        return 0, 0, 0

    aprovado = decisao == "APROVADO"
    item = _linha(sol.solicitacao)[:140]
    parecer = (sol.capa_parecer_auditor or "").strip()
    if aprovado:
        titulo, assunto = "Plano de ação aprovado", f"Plano de ação aprovado: {aud.titulo}"
        intro = f"O plano de ação do item “{item}” foi aprovado pelo auditor."
    else:
        titulo, assunto = "Plano de ação rejeitado", f"Ajuste necessário no plano de ação: {aud.titulo}"
        intro = f"O plano de ação do item “{item}” foi rejeitado e precisa de ajustes. Reabra o link, corrija e reenvie."
    texto = f"{intro}\n" + (f"\nParecer do auditor:\n{parecer}\n" if parecer else "") + (
        "" if aprovado else f"\nResponder novamente: {url}\n")
    corpo = f"<p>{escape(intro)}</p>"
    if parecer:
        corpo += (
            '<blockquote style="border-left:4px solid #cbd5e1;margin:12px 0;padding:4px 14px;color:#475569">'
            f"<strong>Parecer do auditor</strong>{linebreaks(escape(parecer))}</blockquote>"
        )
    enviados, falhas = _enviar(
        destinos, assunto, texto,
        _html(titulo, corpo, None if aprovado else url, "Corrigir o plano de ação"), reply_to=responder_para,
    )
    return enviados, falhas, len(destinos)
