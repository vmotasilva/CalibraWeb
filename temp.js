
document.addEventListener('DOMContentLoaded', function() {
    applyStateFromQuery();
    filtrar();
    const searchInput = document.getElementById('searchInput');
    const checkboxes = document.querySelectorAll('.filter-checkbox');
    searchInput.addEventListener('keyup', function(){ filtrar(); updateExportLink(); updateEtiquetasLink(); renderEtiquetasSummary(); });
    checkboxes.forEach(cb => cb.addEventListener('change', function(){ filtrar(); updateExportLink(); updateEtiquetasLink(); renderEtiquetasSummary(); }));

    // Append filter state to detail links
    document.querySelectorAll('.detail-link').forEach(a => {
        a.addEventListener('click', function(ev){
            ev.preventDefault();
            const state = getFilterState();
            const qs = buildQueryString(state);
            const base = this.getAttribute('href');
            window.location.href = base + (qs ? ('?' + qs) : '');
        });
    });

    // Copy link with current filters
    const btnCopy = document.getElementById('btnCopyFilters');
    if (btnCopy) {
        btnCopy.addEventListener('click', async function(){
            const qs = buildQueryString(getFilterState());
            const url = window.location.origin + window.location.pathname + (qs ? ('?' + qs) : '');
            try {
                await navigator.clipboard.writeText(url);
                btnCopy.innerText = '✅ Copiado!';
                setTimeout(()=> btnCopy.innerText = '🔗 Copiar Link', 1500);
            } catch (e) {
                alert('Não foi possível copiar o link.');
            }
        });
    }

    // Export button points to export endpoint with same query
    const btnExport = document.getElementById('btnExport');
    if (btnExport) {
        updateExportLink();
    }

    const btnEtiquetas = document.getElementById('btnEtiquetas');
    if (btnEtiquetas) {
        updateEtiquetasLink();
        ['etq_orient','etq_cols','etq_rows','etq_margin','etq_pad'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', function(){ updateEtiquetasLink(); renderEtiquetasSummary(); });
            if (el) el.addEventListener('keyup', function(){ updateEtiquetasLink(); renderEtiquetasSummary(); });
        });
    }

    // Atualiza o resumo quando o modal abre (Bootstrap)
    const etqModal = document.getElementById('etqModal');
    if (etqModal) {
        etqModal.addEventListener('shown.bs.modal', function(){
            updateEtiquetasLink();
            renderEtiquetasSummary();
        });
    }
});

function getFilterState() {
    const state = { q: '', st: [], sit: [], cat: [], set: [], res: [] };
    const qEl = document.getElementById('searchInput');
    state.q = (qEl && qEl.value) ? qEl.value : '';
    document.querySelectorAll('.filter-checkbox').forEach(cb => {
        if (!cb.checked) return;
        const val = cb.value;
        switch(cb.dataset.category){
            case 'status': state.st.push(val); break;
            case 'situacao': state.sit.push(val); break;
            case 'categoria': state.cat.push(val); break;
            case 'setor': state.set.push(val); break;
            case 'resultado': state.res.push(val); break;
        }
    });
    return state;
}

function buildQueryString(state){
    const params = [];
    if (state.q) params.push('q=' + encodeURIComponent(state.q));
    if (state.st.length) params.push('st=' + encodeURIComponent(state.st.join(',')));
    if (state.sit.length) params.push('sit=' + encodeURIComponent(state.sit.join(',')));
    if (state.cat.length) params.push('cat=' + encodeURIComponent(state.cat.join(',')));
    if (state.set.length) params.push('set=' + encodeURIComponent(state.set.join(',')));
    if (state.res.length) params.push('res=' + encodeURIComponent(state.res.join(',')));
    return params.join('&');
}

function applyStateFromQuery(){
    const sp = new URLSearchParams(window.location.search);
    const q = sp.get('q') || '';
    const st = (sp.get('st') || '').split(',').filter(Boolean);
    const sit = (sp.get('sit') || '').split(',').filter(Boolean);
    // Dashboard hint: status=vencidos|avencer maps to situacao checkboxes
    const dashStatus = (sp.get('status') || '').toLowerCase();
    if (!sit.length && dashStatus) {
        if (dashStatus === 'vencidos') {
            sit.push('VENCIDO');
        } else if (dashStatus === 'avencer') {
            // Map legacy 'avencer' to all AVENCER_* ranges
            sit.push('AVENCER_30', 'AVENCER_60', 'AVENCER_90', 'AVENCER_120');
        }
    }
    const cat = (sp.get('cat') || '').split(',').filter(Boolean);
    const set = (sp.get('set') || '').split(',').filter(Boolean);
    const res = (sp.get('res') || '').split(',').filter(Boolean);
    const qEl = document.getElementById('searchInput');
    if (qEl) qEl.value = q;
    document.querySelectorAll('.filter-checkbox').forEach(cb => {
        const val = cb.value;
        switch(cb.dataset.category){
            case 'status': cb.checked = st.includes(val) || (st.length===0 && cb.id==='st_ativo'); break;
            case 'situacao': cb.checked = sit.includes(val); break;
            case 'categoria': cb.checked = cat.includes(val); break;
            case 'setor': cb.checked = set.includes(val); break;
            case 'resultado': cb.checked = res.includes(val); break;
        }
    });
}

function toggleFilterGroup(element) {
    element.parentElement.classList.toggle('open');
}

function filtrar() {
    const searchInput = document.getElementById('searchInput');
    const countDisplay = document.getElementById('countDisplay');
    const termoBusca = searchInput.value.toLowerCase();
    
    const filtrosAtivos = { status: [], situacao: [], categoria: [], setor: [], resultado: [] };
    
    document.querySelectorAll('.filter-checkbox').forEach(cb => {
        if (cb.checked) filtrosAtivos[cb.dataset.category].push(cb.value);
    });

    let filteredRows = [];
    
    document.querySelectorAll('.instrumento-row').forEach(row => {
        let mostrar = true;

        if (termoBusca && !row.dataset.nome.includes(termoBusca)) mostrar = false;
        
        if (mostrar && filtrosAtivos.status.length > 0 && !filtrosAtivos.status.includes(row.dataset.status)) mostrar = false;
        if (mostrar && filtrosAtivos.situacao.length > 0 && !filtrosAtivos.situacao.includes(row.dataset.situacao)) mostrar = false;
        if (mostrar && filtrosAtivos.categoria.length > 0 && !filtrosAtivos.categoria.includes(row.dataset.categoria)) mostrar = false;
        if (mostrar && filtrosAtivos.setor.length > 0 && !filtrosAtivos.setor.includes(row.dataset.setor)) mostrar = false;
        if (mostrar && filtrosAtivos.resultado.length > 0 && !filtrosAtivos.resultado.includes(row.dataset.resultado)) mostrar = false;

        if (mostrar) {
            filteredRows.push(row);
        } else {
            row.style.display = 'none';
        }
    });

    if(countDisplay) countDisplay.innerText = filteredRows.length;
    renderPagination(filteredRows);
}

let currentPage = 1;
const itemsPerPage = 15;

function renderPagination(rows) {
    const totalItems = rows.length;
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    
    if (currentPage > totalPages) currentPage = totalPages || 1;
    if (currentPage < 1) currentPage = 1;
    
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = Math.min(startIndex + itemsPerPage, totalItems);
    
    // Esconde todos os filtrados e exibe apenas os da pagina atual
    rows.forEach((row, index) => {
        if (index >= startIndex && index < endIndex) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    
    // Atualiza o info de paginacao
    const info = document.getElementById('paginationInfo');
    if (info) {
        if (totalItems === 0) {
            info.innerText = `Nenhum instrumento encontrado.`;
        } else {
            info.innerText = `Mostrando ${startIndex + 1} a ${endIndex} de ${totalItems} instrumentos`;
        }
    }
    
    // Constroi os botoes
    const controls = document.getElementById('paginationControls');
    if (controls) {
        controls.innerHTML = '';
        if (totalPages > 1) {
            // Botão Anterior
            let liPrev = document.createElement('li');
            liPrev.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
            liPrev.innerHTML = `<a class="page-link" href="#" aria-label="Anterior"><span aria-hidden="true">&laquo;</span></a>`;
            if (currentPage > 1) {
                liPrev.addEventListener('click', (e) => { e.preventDefault(); currentPage--; renderPagination(rows); });
            }
            controls.appendChild(liPrev);
            
            // Botões numéricos limitados (para não quebrar o layout se houver muitas páginas)
            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(totalPages, startPage + 4);
            if (endPage - startPage < 4) {
                startPage = Math.max(1, endPage - 4);
            }
            
            for (let i = startPage; i <= endPage; i++) {
                let li = document.createElement('li');
                li.className = `page-item ${i === currentPage ? 'active' : ''}`;
                li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
                if (i !== currentPage) {
                    li.addEventListener('click', (e) => { e.preventDefault(); currentPage = i; renderPagination(rows); });
                }
                controls.appendChild(li);
            }
            
            // Botão Próximo
            let liNext = document.createElement('li');
            liNext.className = `page-item ${currentPage === totalPages ? 'disabled' : ''}`;
            liNext.innerHTML = `<a class="page-link" href="#" aria-label="Próximo"><span aria-hidden="true">&raquo;</span></a>`;
            if (currentPage < totalPages) {
                liNext.addEventListener('click', (e) => { e.preventDefault(); currentPage++; renderPagination(rows); });
            }
            controls.appendChild(liNext);
        }
    }
}

// Reset page on filter changes (placed properly now)
document.addEventListener('DOMContentLoaded', function() {
    const sInput = document.getElementById('searchInput');
    if (sInput) {
        sInput.addEventListener('keyup', () => { currentPage = 1; });
    }
    document.querySelectorAll('.filter-checkbox').forEach(cb => {
        cb.addEventListener('change', () => { currentPage = 1; });
    });
});
}

function limparFiltros() {
    document.getElementById('searchInput').value = '';
    document.querySelectorAll('.filter-checkbox').forEach(cb => {
        cb.checked = (cb.id === 'st_ativo');
    });
    filtrar();
    updateExportLink();
    updateEtiquetasLink();
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar-col');
    const content = document.getElementById('content-col');
    const icon = document.getElementById('sidebarIcon');

    if (sidebar.classList.contains('d-none')) {
        sidebar.classList.remove('d-none');
        content.classList.replace('col-12', 'col-md-9');
        content.classList.add('col-lg-10');
        icon.classList.replace('bi-layout-sidebar-inset', 'bi-layout-sidebar');
    } else {
        sidebar.classList.add('d-none');
        content.classList.replace('col-md-9', 'col-12');
        content.classList.remove('col-lg-10');
        icon.classList.replace('bi-layout-sidebar', 'bi-layout-sidebar-inset');
    }
}

function updateExportLink(){
    const btnExport = document.getElementById('btnExport');
    if(!btnExport) return;
    const qs = buildQueryString(getFilterState());
    btnExport.href = '{% url 'exportar_instrumentos' %}' + (qs ? ('?' + qs) : '');
}

function updateEtiquetasLink(){
    const btnEtiquetas = document.getElementById('btnEtiquetas');
    if(!btnEtiquetas) return;
    const qs = buildQueryString(getFilterState());
    const orient = (document.getElementById('etq_orient')?.value || 'portrait');
    const cols = (document.getElementById('etq_cols')?.value || 2);
    const rows = (document.getElementById('etq_rows')?.value || 5);
    const margin = (document.getElementById('etq_margin')?.value || 10);
    const pad = (document.getElementById('etq_pad')?.value || 5);
    const extras = `orient=${encodeURIComponent(orient)}&cols=${encodeURIComponent(cols)}&rows=${encodeURIComponent(rows)}&margin_mm=${encodeURIComponent(margin)}&pad_mm=${encodeURIComponent(pad)}`;
    const finalQs = qs ? (qs + '&' + extras) : extras;
    btnEtiquetas.href = '{% url 'metrologia:export_etiquetas' %}' + (finalQs ? ('?' + finalQs) : '');
}

function renderEtiquetasSummary(){
    const box = document.getElementById('etqSummary');
    if(!box) return;
    const countTxt = document.getElementById('countDisplay')?.innerText || '0';
    const count = parseInt(countTxt, 10) || 0;
    const state = getFilterState();
    function fmt(arr){ return arr.length ? arr.join(', ') : 'Todos'; }

    // Coleta nomes legíveis de categorias e setores selecionados
    const catNames = Array.from(document.querySelectorAll('.filter-checkbox[data-category="categoria"]:checked'))
        .map(cb => (cb.nextElementSibling ? cb.nextElementSibling.textContent.trim() : cb.value));
    const setNames = Array.from(document.querySelectorAll('.filter-checkbox[data-category="setor"]:checked'))
        .map(cb => (cb.nextElementSibling ? cb.nextElementSibling.textContent.trim() : cb.value));

    const parts = [];
    parts.push(`<strong>${count}</strong> instrumento${count===1?'':'s'}`);
    if (state.sit.length) parts.push(`Situação: ${fmt(state.sit)}`);
    if (state.st.length) parts.push(`Status: ${fmt(state.st)}`);

    // Monta chips de categoria e setor quando houver seleção
    let chipsHTML = '';
    if (catNames.length) {
        chipsHTML += `<div class=\"mt-1\"><span class=\"me-2 text-muted\">Categorias:</span>` +
            catNames.map(n => `<span class=\"badge bg-light text-dark border me-1\">${n}</span>`).join(' ') + `</div>`;
    }
    if (setNames.length) {
        chipsHTML += `<div class=\"mt-1\"><span class=\"me-2 text-muted\">Setores:</span>` +
            setNames.map(n => `<span class=\"badge bg-light text-dark border me-1\">${n}</span>`).join(' ') + `</div>`;
    }

    box.innerHTML = `Serão geradas etiquetas para ${parts[0]}. <span class=\"ms-2\">${parts.slice(1).join(' • ')}</span>${chipsHTML}`;
}
