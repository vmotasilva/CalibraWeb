/**
 * Mapear Template Fields - JavaScript
 * Gerencia a interatividade do mapeamento de placeholders para PDFs
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeMappingForm();
});

function initializeMappingForm() {
    const form = document.getElementById('form-mapeamento');
    const selects = document.querySelectorAll('.campo-select');
    const placeholderItems = document.querySelectorAll('[data-placeholder]');

    // Event listeners para mudanças nos selects
    selects.forEach(select => {
        select.addEventListener('change', handleSelectChange);
        select.addEventListener('focus', handleSelectFocus);
        select.addEventListener('blur', handleSelectBlur);
    });

    // Listener para clique nos placeholders para scrollar e destacar no PDF
    placeholderItems.forEach(item => {
        item.addEventListener('click', function(e) {
            const placeholder = this.getAttribute('data-placeholder');
            
            // Remover classe highlighted de todos
            placeholderItems.forEach(i => i.classList.remove('highlighted'));
            
            // Adicionar ao clicado
            this.classList.add('highlighted');
            
            highlightPlaceholderInPdf(placeholder);
            
            // Scroll the select into view
            const selectId = `select-${placeholder}`;
            const select = document.getElementById(selectId);
            if (select) {
                select.focus();
            }
        });
        
        // Adicionar estilo de hover
        item.style.cursor = 'pointer';
    });

    // Listener para submissão do formulário
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }

    // Inicializar contadores
    updateMappingCount();
}

/**
 * Destaca um placeholder no PDF com animação
 */
function highlightPlaceholderInPdf(placeholder) {
    // Criar um estilo visual de destaque
    const pdfFrame = document.querySelector('.pdf-frame');
    if (pdfFrame) {
        // Adicionar classe de destaque
        pdfFrame.style.border = '3px solid #ffb300';
        pdfFrame.style.boxShadow = '0 0 15px rgba(255, 179, 0, 0.5)';
        
        // Remove o destaque depois de 2 segundos
        setTimeout(() => {
            pdfFrame.style.border = '1px solid #ddd';
            pdfFrame.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        }, 2000);
    }
    
    // Mostrar tooltip com informação
    console.log(`Destacar placeholder: ${placeholder}`);
}

/**
 * Atualiza o contador de mapeamentos e visual da interface
 */
function updateMappingCount() {
    const selects = document.querySelectorAll('.campo-select');
    let mapped = 0;

    selects.forEach(select => {
        if (select.value) {
            mapped++;
        }
    });

    const total = selects.length;
    const pending = total - mapped;

    // Atualizar badges de estatísticas
    updateStatBadges(total, mapped, pending);

    // Atualizar progress bar
    updateProgressBar(mapped, total);

    // Atualizar visual dos itens
    updateMappingItemsVisual();

    // Habilitar/desabilitar botão de submit
    updateSubmitButton(mapped, total);
}

/**
 * Atualiza os badges de estatísticas
 */
function updateStatBadges(total, mapped, pending) {
    const mappedCount = document.getElementById('mapped-count');
    const pendingCount = document.getElementById('pending-count');

    if (mappedCount) {
        mappedCount.textContent = mapped;
        mappedCount.style.animation = 'none';
        setTimeout(() => {
            mappedCount.style.animation = 'slideIn 0.3s ease';
        }, 10);
    }

    if (pendingCount) {
        pendingCount.textContent = pending;
        pendingCount.style.animation = 'none';
        setTimeout(() => {
            pendingCount.style.animation = 'slideIn 0.3s ease';
        }, 10);
    }
}

/**
 * Atualiza a progress bar visual
 */
function updateProgressBar(mapped, total) {
    const progressText = document.getElementById('progress-text');
    const progressFill = document.getElementById('progress-fill');

    if (progressText) {
        progressText.textContent = mapped + ' / ' + total + ' mapeados';
    }

    if (progressFill) {
        const percentage = total > 0 ? (mapped / total) * 100 : 0;
        progressFill.style.width = percentage + '%';

        // Adicionar cor verde se completo
        if (percentage === 100 && total > 0) {
            progressFill.style.background = 'linear-gradient(90deg, #10b981, #059669)';
        }
    }
}

/**
 * Atualiza o visual dos itens de mapeamento
 */
function updateMappingItemsVisual() {
    const selects = document.querySelectorAll('.campo-select');

    selects.forEach(select => {
        const item = select.closest('.mapping-item');
        if (item) {
            if (select.value) {
                item.classList.remove('incomplete');
                item.classList.add('complete');
            } else {
                item.classList.remove('complete');
                item.classList.add('incomplete');
            }
        }
    });
}

/**
 * Atualiza o estado do botão de submit
 */
function updateSubmitButton(mapped, total) {
    const btnSubmit = document.getElementById('btn-submit');

    if (btnSubmit) {
        // Permitir submissão se pelo menos um placeholder foi mapeado
        if (mapped > 0) {
            btnSubmit.disabled = false;
            btnSubmit.style.opacity = '1';
            btnSubmit.style.cursor = 'pointer';
        } else {
            btnSubmit.disabled = true;
            btnSubmit.style.opacity = '0.6';
            btnSubmit.style.cursor = 'not-allowed';
        }
    }
}

/**
 * Handler para mudança de select
 */
function handleSelectChange(event) {
    const select = event.target;
    const selectedOption = select.options[select.selectedIndex];

    // Adicionar feedback visual
    if (select.value) {
        select.style.borderColor = '#10b981';
        select.style.background = '#f0fdf4';
    } else {
        select.style.borderColor = '#ddd';
        select.style.background = 'white';
    }

    updateMappingCount();
}

/**
 * Handler para focus do select
 */
function handleSelectFocus(event) {
    const select = event.target;
    select.style.borderColor = '#667eea';
    select.style.boxShadow = '0 0 0 3px rgba(102, 126, 234, 0.1)';
}

/**
 * Handler para blur do select
 */
function handleSelectBlur(event) {
    const select = event.target;
    if (!select.value) {
        select.style.borderColor = '#f59e0b';
    } else {
        select.style.borderColor = '#10b981';
    }
    select.style.boxShadow = 'none';
}

/**
 * Handler para submissão do formulário
 */
function handleFormSubmit(event) {
    const selects = document.querySelectorAll('.campo-select');
    let anyMapped = false;

    selects.forEach(select => {
        if (select.value) {
            anyMapped = true;
        }
    });

    if (!anyMapped) {
        event.preventDefault();
        showError('Você deve mapear pelo menos um placeholder!');
        return false;
    }

    // Mostrar loading
    const btnSubmit = document.getElementById('btn-submit');
    if (btnSubmit) {
        const originalText = btnSubmit.innerHTML;
        btnSubmit.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
        btnSubmit.disabled = true;

        // Restaurar após a submissão
        setTimeout(() => {
            btnSubmit.innerHTML = originalText;
            btnSubmit.disabled = false;
        }, 1000);
    }
}

/**
 * Mostra mensagem de erro
 */
function showError(message) {
    // Criar elemento de alerta se não existir
    let alertElement = document.querySelector('.alert-custom-error');

    if (!alertElement) {
        alertElement = document.createElement('div');
        alertElement.className = 'alert alert-danger alert-custom-error';
        alertElement.style.position = 'fixed';
        alertElement.style.top = '20px';
        alertElement.style.right = '20px';
        alertElement.style.maxWidth = '400px';
        alertElement.style.zIndex = '9999';
        alertElement.style.animation = 'slideIn 0.3s ease';
        document.body.appendChild(alertElement);
    }

    alertElement.innerHTML = '<i class="fas fa-exclamation-circle"></i> ' + message;
    alertElement.style.display = 'block';

    // Auto-fechar após 3 segundos
    setTimeout(() => {
        alertElement.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            alertElement.style.display = 'none';
        }, 300);
    }, 3000);
}

/**
 * Adiciona interatividade ao preview do PDF
 */
function initializePDFInteraction() {
    const pdfFrame = document.querySelector('.pdf-frame');
    const placeholderItems = document.querySelectorAll('.mapping-item');

    if (pdfFrame && placeholderItems.length > 0) {
        placeholderItems.forEach(item => {
            item.addEventListener('click', function() {
                // Highlight do item ao clicar
                const wasHighlighted = this.style.backgroundColor === 'rgba(102, 126, 234, 0.1)';
                placeholderItems.forEach(i => {
                    i.style.backgroundColor = 'transparent';
                    i.style.borderLeft = '4px solid #e0e0e0';
                });

                if (!wasHighlighted) {
                    this.style.backgroundColor = 'rgba(102, 126, 234, 0.1)';
                    this.style.borderLeft = '4px solid #667eea';
                }
            });
        });
    }
}

/**
 * Suportar atalhos de teclado
 */
document.addEventListener('keydown', function(event) {
    // Ctrl+S ou Cmd+S para salvar
    if ((event.ctrlKey || event.metaKey) && event.key === 's') {
        event.preventDefault();
        const form = document.getElementById('form-mapeamento');
        const btnSubmit = document.getElementById('btn-submit');
        if (form && btnSubmit) {
            form.submit();
        }
    }
});

// Inicializar interatividade do PDF ao carregar
window.addEventListener('load', initializePDFInteraction);

// PDF Upload Handler
document.addEventListener('DOMContentLoaded', function() {
    const pdfUploadInput = document.getElementById('pdf-upload');
    const btnRemovePdf = document.getElementById('btn-remove-pdf');
    
    if (pdfUploadInput) {
        pdfUploadInput.addEventListener('change', handlePdfUpload);
    }
    
    if (btnRemovePdf) {
        btnRemovePdf.addEventListener('click', handleRemovePdf);
    }
});

async function handlePdfUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    // Validar tipo de arquivo
    if (!file.type.includes('pdf')) {
        alert('Por favor, selecione um arquivo PDF válido');
        return;
    }
    
    const formData = new FormData();
    formData.append('pdf_file', file);
    
    // Obter template ID da URL
    const templateId = window.location.pathname.match(/(\d+)/)[1];
    
    try {
        const response = await fetch(`/procedures/templates-presenca/${templateId}/upload-pdf/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        if (response.ok) {
            alert('PDF carregado com sucesso!');
            location.reload(); // Recarregar página para exibir novo PDF
        } else {
            const error = await response.json();
            alert(`Erro: ${error.message || 'Falha ao carregar PDF'}`);
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao carregar PDF');
    }
}

async function handleRemovePdf() {
    if (!confirm('Tem certeza que deseja remover o PDF?')) {
        return;
    }
    
    const templateId = window.location.pathname.match(/(\d+)/)[1];
    
    try {
        const response = await fetch(`/procedures/templates-presenca/${templateId}/remove-pdf/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        if (response.ok) {
            alert('PDF removido com sucesso!');
            location.reload();
        } else {
            const error = await response.json();
            alert(`Erro: ${error.message || 'Falha ao remover PDF'}`);
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao remover PDF');
    }
}

function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
