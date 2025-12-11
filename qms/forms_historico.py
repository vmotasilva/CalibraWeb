from django import forms
from django.core.exceptions import ValidationError
from metrologia.models import HistoricoCalibracao, ArquivoPadrao

def validate_pdf_file(file):
    """Validate that uploaded file is a PDF."""
    valid_mime_types = ['application/pdf']
    
    # Check file extension
    if not file.name.lower().endswith('.pdf'):
        raise ValidationError('O arquivo deve ser um PDF. Extensão inválida.')
    
    # Check MIME type if available
    if hasattr(file, 'content_type'):
        if file.content_type not in valid_mime_types:
            raise ValidationError(f'Tipo de arquivo inválido: {file.content_type}. Deve ser PDF.')
    
    # Check file size (max 50MB)
    if file.size > 50 * 1024 * 1024:
        raise ValidationError('Arquivo muito grande. Máximo permitido: 50MB.')
    
    return file

class HistoricoCalibracaoForm(forms.ModelForm):
    # Campo adicional para upload de novos arquivos de padrão
    novos_arquivos_padroes = forms.FileField(
        label='Fazer Upload de Novos Padrões',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf',
        }),
        validators=[validate_pdf_file]
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
            'certificado': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
            'resultado': forms.Select(attrs={'class': 'form-select'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'arquivos_padroes': forms.CheckboxSelectMultiple(attrs={'class': 'padroes-checkbox'}),
        }
    
    def clean_certificado(self):
        """Validate certificate file."""
        certificado = self.cleaned_data.get('certificado')
        if certificado:
            return validate_pdf_file(certificado)
        return certificado
    
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
