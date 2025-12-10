from django import forms
from metrologia.models import HistoricoCalibracao, ArquivoPadrao

class HistoricoCalibracaoForm(forms.ModelForm):
    # Campo adicional para upload de novos arquivos de padrão
    novos_arquivos_padroes = forms.FileField(
        label='Fazer Upload de Novos Padrões',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf',
        })
    )
    
    class Meta:
        model = HistoricoCalibracao
        fields = [
            'data_calibracao',
            'data_aprovacao',
            'numero_certificado',
            'tem_selo_rbc',
            'tipo_calibracao',
            'responsavel',
            'fornecedor',
            'erro_encontrado',
            'incerteza',
            'tolerancia_usada',
            'proxima_calibracao',
            'certificado',
            'resultado',
            'observacoes',
            'arquivos_padroes',
        ]
        widgets = {
            'data_calibracao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_aprovacao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'numero_certificado': forms.TextInput(attrs={'class': 'form-control'}),
            'tem_selo_rbc': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tipo_calibracao': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.TextInput(attrs={'class': 'form-control'}),
            'fornecedor': forms.TextInput(attrs={'class': 'form-control'}),
            'erro_encontrado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'incerteza': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'tolerancia_usada': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'proxima_calibracao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'certificado': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'resultado': forms.Select(attrs={'class': 'form-select'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'arquivos_padroes': forms.CheckboxSelectMultiple(attrs={'class': 'padroes-checkbox'}),
        }
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Processar upload de novos arquivos de padrão
        if self.files.getlist('novos_arquivos_padroes'):
            for uploaded_file in self.files.getlist('novos_arquivos_padroes'):
                # Criar novo ArquivoPadrao
                novo_padrao = ArquivoPadrao.objects.create(
                    nome=uploaded_file.name.replace('.pdf', ''),
                    descricao='',
                    arquivo=uploaded_file
                )
                # Adicionar ao formulário
                instance.arquivos_padroes.add(novo_padrao)
        
        if commit:
            instance.save()
        
        return instance
