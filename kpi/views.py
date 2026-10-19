from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from kpi.forms import IndicadorForm, MedicaoForm
from kpi.models import Indicador, Medicao


@login_required
def painel_view(request):
    """Painel: último valor de cada indicador ativo vs. meta."""
    cards = []
    for ind in Indicador.objects.filter(ativo=True).prefetch_related('medicoes'):
        meds = list(ind.medicoes.all()[:6])
        ultima = meds[0] if meds else None
        cards.append({
            'ind': ind,
            'ultima': ultima,
            'atingiu': ind.atingiu(ultima.valor) if ultima else None,
            'serie': list(reversed(meds)),
        })
    total = len(cards)
    ok = sum(1 for c in cards if c['atingiu'] is True)
    fora = sum(1 for c in cards if c['atingiu'] is False)
    return render(request, 'kpi/painel.html', {
        'cards': cards, 'total': total, 'ok': ok, 'fora': fora, 'sem_dado': total - ok - fora,
    })


@login_required
def indicadores_view(request):
    return render(request, 'kpi/indicadores.html', {'indicadores': Indicador.objects.all()})


@login_required
def indicador_form_view(request, pk=None):
    ind = get_object_or_404(Indicador, pk=pk) if pk else None
    form = IndicadorForm(request.POST or None, instance=ind)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if not ind:
            obj.criado_por = request.user
        obj.save()
        messages.success(request, 'Indicador salvo.')
        return redirect('kpi:indicador_detalhe', pk=obj.pk)
    return render(request, 'kpi/indicador_form.html', {'form': form, 'ind': ind})


@login_required
def indicador_detalhe_view(request, pk):
    ind = get_object_or_404(Indicador, pk=pk)
    form = MedicaoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        Medicao.objects.update_or_create(
            indicador=ind, periodo=form.cleaned_data['periodo'],
            defaults={
                'valor': form.cleaned_data['valor'],
                'observacao': form.cleaned_data['observacao'],
                'registrado_por': request.user,
            },
        )
        messages.success(request, 'Medição registrada.')
        return redirect('kpi:indicador_detalhe', pk=ind.pk)
    meds = list(ind.medicoes.all())
    for m in meds:
        m.atingiu = ind.atingiu(m.valor)
    serie = list(reversed(meds[:24]))
    return render(request, 'kpi/indicador_detalhe.html', {
        'ind': ind, 'form': form, 'medicoes': meds,
        'dados': {
            'labels': [m.periodo.strftime('%m/%Y') for m in serie],
            'valores': [float(m.valor) for m in serie],
            'meta': float(ind.meta),
        },
    })


@login_required
@require_POST
def indicador_excluir_view(request, pk):
    get_object_or_404(Indicador, pk=pk).delete()
    messages.success(request, 'Indicador excluído.')
    return redirect('kpi:indicadores')


@login_required
@require_POST
def medicao_excluir_view(request, pk):
    m = get_object_or_404(Medicao, pk=pk)
    ind_pk = m.indicador_id
    m.delete()
    return redirect('kpi:indicador_detalhe', pk=ind_pk)
