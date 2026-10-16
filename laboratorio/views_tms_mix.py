"""TMS - Mix de materiais e amostras de tempo (TC ponderado pela demanda)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import AmostraTempoTMS, EtapaProcessoTMS, FluxoProcessoTMS, MaterialTMS


def _parse_tempo(txt):
    """Aceita '90', '90,5' ou 'm:ss' / 'h:mm:ss' e devolve segundos (ou None)."""
    txt = (txt or "").strip().replace(",", ".")
    if not txt:
        return None
    try:
        if ":" in txt:
            total = 0.0
            for parte in txt.split(":"):
                total = total * 60 + float(parte)
            return total
        return float(txt)
    except ValueError:
        return None


@login_required
def tms_mix_materiais(request, fluxo_id):
    """Cadastra os materiais do fluxo e o percentual de demanda de cada um."""
    fluxo = get_object_or_404(FluxoProcessoTMS, id=fluxo_id)
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "adicionar":
            nome = (request.POST.get("nome") or "").strip()
            pct = _parse_tempo(request.POST.get("percentual"))
            if not nome or pct is None or not (0 <= pct <= 100):
                messages.error(request, "Informe o nome e um percentual entre 0 e 100.")
            elif MaterialTMS.objects.filter(fluxo=fluxo, nome__iexact=nome).exists():
                messages.error(request, f"O material '{nome}' já existe neste fluxo.")
            else:
                MaterialTMS.objects.create(fluxo=fluxo, nome=nome, percentual_demanda=pct)
        elif acao == "salvar":
            for mat in fluxo.materiais.all():
                pct = _parse_tempo(request.POST.get(f"pct_{mat.id}"))
                if pct is not None and 0 <= pct <= 100:
                    mat.percentual_demanda = pct
                mat.ativo = request.POST.get(f"ativo_{mat.id}") == "on"
                mat.save()
            messages.success(request, "Mix atualizado.")
        elif acao == "excluir":
            fluxo.materiais.filter(id=request.POST.get("material_id")).delete()
        return redirect("laboratorio:tms_mix_materiais", fluxo_id=fluxo.id)

    materiais = list(fluxo.materiais.all())
    total = sum(float(m.percentual_demanda) for m in materiais if m.ativo)
    return render(request, "laboratorio/tms_mix_materiais.html", {
        "fluxo": fluxo, "materiais": materiais, "total_pct": round(total, 2),
    })


@login_required
def tms_etapa_amostras(request, pk):
    """Registro de tempos por material em uma etapa e cálculo do TC médio ponderado."""
    etapa = get_object_or_404(EtapaProcessoTMS, pk=pk)
    fluxo = etapa.fluxo
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "limpar":
            etapa.amostras_tempo.filter(material_id=request.POST.get("material_id")).delete()
        elif acao == "excluir":
            etapa.amostras_tempo.filter(id=request.POST.get("amostra_id")).delete()
        else:
            material = fluxo.materiais.filter(id=request.POST.get("material_id")).first()
            valores = [_parse_tempo(v) for v in (request.POST.get("tempos") or "").replace(";", " ").split()]
            if not material:
                messages.error(request, "Selecione um material.")
            elif not valores or any(v is None or v <= 0 for v in valores):
                messages.error(request, "Informe tempos válidos (segundos ou m:ss), separados por espaço.")
            else:
                AmostraTempoTMS.objects.bulk_create(
                    [AmostraTempoTMS(etapa=etapa, material=material, segundos=v) for v in valores]
                )
                messages.success(request, f"{len(valores)} amostra(s) registrada(s) para {material.nome}.")
        return redirect("laboratorio:tms_etapa_amostras", pk=etapa.id)

    medias = etapa.medias_por_material()
    linhas = []
    for mat in fluxo.materiais.filter(ativo=True):
        amostras = list(etapa.amostras_tempo.filter(material=mat))
        media = medias.get(mat.id)
        linhas.append({
            "material": mat,
            "amostras": amostras,
            "media": round(media, 2) if media is not None else None,
            "contribuicao": round(media * float(mat.percentual_demanda) / 100.0, 2) if media is not None else None,
        })
    ponderado = etapa.tempo_ciclo_ponderado()
    return render(request, "laboratorio/tms_etapa_amostras.html", {
        "etapa": etapa, "fluxo": fluxo, "linhas": linhas,
        "ponderado": round(ponderado, 2) if ponderado is not None else None,
        "total_pct": round(sum(float(m.percentual_demanda) for m in fluxo.materiais.filter(ativo=True)), 2),
    })
