from django.shortcuts import get_object_or_404, render
from .models import RegistroTreinamento


def treinamentos_detalhe_view(request, treinamento_id):
    treinamento = get_object_or_404(RegistroTreinamento, id=treinamento_id)
    return render(request, 'training/treinamento_detalhe.html', {
        'treinamento': treinamento
    })

def novo_treinamento_view(request):
    if request.method == 'POST':
        form = RegistroTreinamentoForm(request.POST)
        if form.is_valid():
            treinamento = form.save()
            messages.success(request, 'Treinamento registrado com sucesso.')
            return redirect('treinamentos_lista')
    else:
        form = RegistroTreinamentoForm()
    return render(request, 'training/treinamento_form.html', {
        'form': form
    })

def editar_treinamento_view(request, treinamento_id):
    treinamento = get_object_or_404(RegistroTreinamento, id=treinamento_id)
    if request.method == 'POST':
        form = RegistroTreinamentoForm(request.POST, instance=treinamento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Treinamento atualizado.')
            return redirect('treinamentos_lista')
    else:
        form = RegistroTreinamentoForm(instance=treinamento)
    return render(request, 'training/treinamento_form.html', {
        'form': form
    })
