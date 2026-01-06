/**
 * PDF Viewer com suporte a click-mode para marcar placeholders
 */

// Configurar worker do PDF.js
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

let pdfDoc = null;
let currentPage = 1;
let totalPages = 0;
let pdfUrl = null;
let clickMode = false;

// Inicializar PDF viewer
document.addEventListener('DOMContentLoaded', async function() {
    console.log('[PDF Viewer] Iniciando...');
    
    const canvas = document.getElementById('pdf-canvas');
    const pageNum = document.getElementById('pdf-page-num');
    const totalPagesSpan = document.getElementById('pdf-total-pages');
    const prevBtn = document.getElementById('pdf-prev');
    const nextBtn = document.getElementById('pdf-next');
    const searchInput = document.getElementById('pdf-search-input');
    const clickModeToggle = document.getElementById('pdf-click-mode');
    
    console.log('[PDF Viewer] Canvas encontrado:', !!canvas);
    
    // Obter URL do PDF - tenta window.PDF_URL primeiro, depois busca no link
    pdfUrl = window.PDF_URL || null;
    
    if (!pdfUrl) {
        const pdfLink = document.querySelector('a[href*="/pdf/"]');
        if (pdfLink) {
            pdfUrl = pdfLink.href;
        }
    }
    
    console.log('[PDF Viewer] PDF URL:', pdfUrl);

    // Carregar PDF
    if (pdfUrl && canvas) {
        try {
            console.log('[PDF Viewer] Carregando PDF de:', pdfUrl);
            
            // Mostrar status de carregamento
            const container = document.getElementById('pdf-canvas-container');
            if (container) {
                const statusDiv = document.createElement('div');
                statusDiv.id = 'pdf-loading-status';
                statusDiv.style.cssText = 'text-align: center; padding: 20px; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%;';
                statusDiv.textContent = 'Carregando PDF...';
                container.style.position = 'relative';
                container.appendChild(statusDiv);
            }
            
            pdfDoc = await pdfjsLib.getDocument(pdfUrl).promise;
            totalPages = pdfDoc.numPages;
            console.log('[PDF Viewer] PDF carregado com sucesso. Páginas:', totalPages);
            totalPagesSpan.textContent = totalPages;
            
            // Remover status de carregamento
            const statusDiv = document.getElementById('pdf-loading-status');
            if (statusDiv) {
                statusDiv.remove();
            }
            
            // Renderizar primeira página
            renderPage(1);
            
            // Event listeners
            if (prevBtn) prevBtn.addEventListener('click', () => previousPage());
            if (nextBtn) nextBtn.addEventListener('click', () => nextPage());
            if (pageNum) pageNum.addEventListener('change', () => goToPage(parseInt(pageNum.value) || 1));
            if (searchInput) searchInput.addEventListener('input', () => searchText(searchInput.value));
            
            // Click mode toggle
            if (clickModeToggle) {
                clickModeToggle.addEventListener('change', function() {
                    clickMode = this.checked;
                    canvas.style.cursor = clickMode ? 'crosshair' : 'default';
                });
            }
            
            // Click handler para o canvas
            canvas.addEventListener('click', function(e) {
                if (clickMode) {
                    handleCanvasClick(e, canvas);
                }
            });
            
        } catch (error) {
            console.error('[PDF Viewer] Erro ao carregar PDF:', error);
            const statusDiv = document.getElementById('pdf-loading-status');
            if (statusDiv) {
                statusDiv.textContent = 'Erro ao carregar PDF: ' + error.message;
                statusDiv.style.color = 'red';
            }
        }
    } else {
        console.log('[PDF Viewer] Nenhum PDF URL ou canvas encontrado');
        console.log('[PDF Viewer] pdfUrl:', pdfUrl, 'canvas:', !!canvas);
    }
});

async function renderPage(num) {
    if (!pdfDoc || num < 1 || num > totalPages) {
        console.error('[PDF Viewer] renderPage: pdfDoc ou página inválida. pdfDoc:', !!pdfDoc, 'num:', num, 'totalPages:', totalPages);
        return;
    }
    
    currentPage = num;
    const pageNum = document.getElementById('pdf-page-num');
    if (pageNum) {
        pageNum.value = num;
    }
    
    try {
        const canvas = document.getElementById('pdf-canvas');
        if (!canvas) {
            console.error('[PDF Viewer] Canvas não encontrado');
            return;
        }
        
        console.log('[PDF Viewer] Renderizando página', num);
        const page = await pdfDoc.getPage(num);
        const ctx = canvas.getContext('2d');
        
        const viewport = page.getViewport({ scale: 1.5 });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        
        await page.render({
            canvasContext: ctx,
            viewport: viewport
        }).promise;
        
        console.log('[PDF Viewer] Página', num, 'renderizada com sucesso');
    } catch (error) {
        console.error('[PDF Viewer] Erro ao renderizar página', num, ':', error);
    }
}

function previousPage() {
    if (currentPage > 1) renderPage(currentPage - 1);
}

function nextPage() {
    if (currentPage < totalPages) renderPage(currentPage + 1);
}

function goToPage(num) {
    if (num >= 1 && num <= totalPages) renderPage(num);
}

async function searchText(searchTerm) {
    if (!pdfDoc || !searchTerm) return;
    
    const canvas = document.getElementById('pdf-canvas');
    
    // Procurar o termo
    let found = false;
    for (let i = 1; i <= totalPages; i++) {
        const page = await pdfDoc.getPage(i);
        const textContent = await page.getTextContent();
        
        for (const item of textContent.items) {
            if (item.str.toLowerCase().includes(searchTerm.toLowerCase())) {
                found = true;
                if (i !== currentPage) {
                    renderPage(i);
                }
                break;
            }
        }
        if (found) break;
    }
    
    // Se encontrou, destacar a área
    if (found) {
        canvas.style.filter = 'brightness(1.1) drop-shadow(0 0 10px #ffb300)';
    } else {
        canvas.style.filter = 'brightness(1)';
    }
}

function handleCanvasClick(e, canvas) {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Obter lista ÚNICA de placeholders (apenas os .mapping-item, não os selects)
    const placeholders = Array.from(document.querySelectorAll('.mapping-item')).map(item => 
        item.getAttribute('data-placeholder')
    ).filter((placeholder, index, self) => self.indexOf(placeholder) === index);
    
    if (placeholders.length === 0) {
        alert('Nenhum placeholder disponível para selecionar');
        return;
    }
    
    console.log('[PDF Viewer] Placeholders únicos encontrados:', placeholders);
    
    // Mostrar modal/popup para selecionar placeholder
    showPlaceholderSelector(x, y, placeholders);
}

function showPlaceholderSelector(x, y, placeholders) {
    // Remover seletor anterior se existir
    const existingSelector = document.getElementById('placeholder-selector-popup');
    if (existingSelector) existingSelector.remove();
    
    // Criar popup
    const popup = document.createElement('div');
    popup.id = 'placeholder-selector-popup';
    popup.className = 'placeholder-selector-popup';
    popup.style.position = 'fixed';
    popup.style.left = (x + 120) + 'px';
    popup.style.top = (y - 20) + 'px';
    popup.style.zIndex = '10000';
    
    let html = '<div class="popup-content"><h6>Selecione o Placeholder:</h6><div class="placeholder-list">';
    placeholders.forEach(placeholder => {
        html += '<button class="placeholder-btn" data-placeholder="' + placeholder + '">{{' + placeholder + '}}</button>';
    });
    html += '</div><button class="btn-close-popup" onclick="document.getElementById(\'placeholder-selector-popup\').remove();">Cancelar</button></div>';
    
    popup.innerHTML = html;
    document.body.appendChild(popup);
    
    // Event listeners para os botões
    popup.querySelectorAll('.placeholder-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const placeholder = this.getAttribute('data-placeholder');
            selectPlaceholder(placeholder);
            popup.remove();
        });
    });
}

function selectPlaceholder(placeholder) {
    console.log('[PDF Viewer] Selecionando placeholder:', placeholder);
    
    // Highlight no placeholder panel - remover de todos
    document.querySelectorAll('.mapping-item').forEach(item => {
        item.classList.remove('highlighted');
    });
    
    // Adicionar highlight ao selecionado
    const placeholderItem = document.querySelector('.mapping-item[data-placeholder="' + placeholder + '"]');
    if (placeholderItem) {
        placeholderItem.classList.add('highlighted');
        placeholderItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        console.log('[PDF Viewer] Placeholder item destacado:', placeholder);
    }
    
    // Focar no select e abrir dropdown
    const select = document.querySelector('select[data-placeholder="' + placeholder + '"]');
    if (select) {
        select.focus();
        // Abrir o dropdown (simular clique)
        const event = new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window
        });
        select.dispatchEvent(event);
        console.log('[PDF Viewer] Select focado para:', placeholder);
    } else {
        console.warn('[PDF Viewer] Select não encontrado para:', placeholder);
    }
}

// Integração com placeholders (clique na direita)
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-placeholder]').forEach(item => {
        item.addEventListener('click', async function(e) {
            if (!clickMode) {
                const placeholder = this.getAttribute('data-placeholder');
                
                // Remover destaque anterior
                document.querySelectorAll('[data-placeholder]').forEach(i => i.classList.remove('highlighted'));
                this.classList.add('highlighted');
                
                // Buscar placeholder no PDF
                const searchTerm = '{{' + placeholder + '}}';
                await searchText(searchTerm);
            }
        });
    });
});
