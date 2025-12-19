from django import forms
from django.core.exceptions import ValidationError
from metrologia.models import HistoricoCalibracao, ArquivoPadrao


class MultipleFileInput(forms.ClearableFileInput):
    """Widget customizado que suporta múltiplos uploads de arquivo."""
    allow_multiple_selected = True


def validate_pdf_file(file):
    """Validate that uploaded file is a PDF."""
    valid_mime_types = ['application/pdf']
    
    # Check file extension
    if not file.name.lower().endswith('.pdf'):
        raise ValidationError('O arquivo deve ser um PDF. Extensão inválida.')
    
    # Check MIME type if available (mais permissivo para uploads múltiplos)
    if hasattr(file, 'content_type') and file.content_type:
        if file.content_type not in valid_mime_types and 'pdf' not in file.content_type.lower():
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
        widget=MultipleFileInput(attrs={
            'class': 'form-control form-control-sm',
            'accept': '.pdf',
        })
    )
    
    # Campos com required=False para permitir atualização parcial
    data_aprovacao = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Data da Aprovação'
    )
    resultado = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        choices=[('', '---')] + list(HistoricoCalibracao.RESULTADO_CHOICES)
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
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'arquivos_padroes': forms.CheckboxSelectMultiple(attrs={'class': 'padroes-checkbox'}),
        }
    
    def clean_certificado(self):
        """Validate certificate file."""
        certificado = self.cleaned_data.get('certificado')
        if certificado and hasattr(certificado, 'name'):
            # Só valida se houver arquivo
            return validate_pdf_file(certificado)
        return certificado
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Salvar instância primeiro se houver mudanças no modelo
        if commit:
            instance.save()
        
        # Processar upload de novos arquivos de padrão (depois de salvar a instância)
        uploaded_files = self.files.getlist('novos_arquivos_padroes') if self.files else []
        for uploaded_file in uploaded_files:
            if uploaded_file:  # Verificar se o arquivo não está vazio
                try:
                    # Validar arquivo PDF
                    validate_pdf_file(uploaded_file)
                    
                    # Criar novo ArquivoPadrao
                    novo_padrao = ArquivoPadrao.objects.create(
                        nome=uploaded_file.name.replace('.pdf', ''),
                        descricao='',
                        arquivo=uploaded_file
                    )
                    # Adicionar ao formulário
                    instance.arquivos_padroes.add(novo_padrao)
                except ValidationError as e:
                    # Log do erro de validação, mas não bloqueia o save
                    print(f"Erro de validação ao processar arquivo {getattr(uploaded_file, 'name', 'desconhecido')}: {str(e)}")
                except Exception as e:
                    # Log do erro, mas não bloqueia o save
                    print(f"Erro ao processar arquivo {getattr(uploaded_file, 'name', 'desconhecido')}: {str(e)}")
        
        return instance
