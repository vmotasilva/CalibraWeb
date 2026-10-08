/* Editor de Diagramas (DOC.071) - módulo "acoes_qms"
 * Ações de governança QMS: submeter, aprovar, devolver, nova revisão, PDF e modelos.
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

// =========================================================================
// AÇÕES QMS (SUBMETER, APROVAR, NOVA REVISÃO, EXPORTAR PDF, TEMPLATES)
// =========================================================================
async function submeterParaAprovacao() {
    if (!confirm("Deseja submeter este fluxograma para aprovação formal de qualidade?")) return;

    const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/submeter/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF_TOKEN }
    });

    if (resp.ok) {
        location.reload();
    } else {
        const data = await resp.json();
        alert("Erro: " + (data.error || "Não foi possível submeter."));
    }
}

async function aprovarVersao() {
    if (!confirm("Atenção: A aprovação tornará esta versão IMUTÁVEL e oficial no QMS. Deseja confirmar?")) return;

    const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/aprovar/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF_TOKEN }
    });

    if (resp.ok) {
        location.reload();
    } else {
        const data = await resp.json();
        alert("Erro: " + (data.error || "Não foi possível aprovar."));
    }
}

async function devolverParaAjustes() {
    const motivo = prompt("Informe o motivo da devolução ao elaborador (obrigatório):");
    if (motivo === null) return;
    if (motivo.trim().length < 5) {
        alert("Informe um motivo com pelo menos 5 caracteres.");
        return;
    }

    const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/devolver/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify({ motivo: motivo.trim() })
    });

    if (resp.ok) {
        location.reload();
    } else {
        const data = await resp.json();
        alert("Erro: " + (data.error || "Não foi possível devolver."));
    }
}

function modalNovaRevisao() {
    const modal = new bootstrap.Modal(document.getElementById('modalNovaRevisao'));
    modal.show();
}

async function confirmarNovaRevisao() {
    const motivo = document.getElementById('motivoNovaRevisao').value.trim();
    if (!motivo) {
        alert("Por favor, preencha o motivo da nova revisão.");
        return;
    }

    const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/criar-nova-revisao/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify({ motivo_revisao: motivo })
    });

    if (resp.ok) {
        const novaVersao = await resp.json();
        window.location.href = `/procedures/diagramas/editor/${novaVersao.id}/`;
    } else {
        const data = await resp.json();
        alert("Erro: " + (data.error || "Falha ao criar nova revisão."));
    }
}

async function exportarPDFDoc071() {
    const btn = event.currentTarget;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Gerando PDF...';
    btn.disabled = true;

    try {
        const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/exportar-pdf-doc071/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
            body: JSON.stringify({ image_base64: null })
        });

        if (resp.ok) {
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const cd = resp.headers.get('Content-Disposition') || '';
            const m = cd.match(/filename="([^"]+)"/);
            a.download = m ? m[1] : `Diagrama_Rev${String(VERSAO_REVISAO).padStart(2, "0")}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } else {
            let msg = "Erro ao gerar PDF.";
            try { msg = (await resp.json()).error || msg; } catch (e) {}
            alert(msg);
        }
    } catch (err) {
        alert("Erro de comunicação ao gerar o relatório.");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function aplicarTemplateSelecionado(templateId) {
    if (!confirm("Deseja aplicar esta estrutura ao diagrama? A topologia atual não salva será substituída pelo modelo.")) return;

    try {
        const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/aplicar-template/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({ template_id: templateId })
        });

        if (resp.ok) {
            const versaoAtualizada = await resp.json();
            topologia = versaoAtualizada.dados_topologia || { nodes: [], edges: [], grid_data: [] };
            if (versaoAtualizada.atualizado_em) versaoAtualizadoEm = versaoAtualizada.atualizado_em;
            registrarHistorico(); // aplicar modelo também pode ser desfeito
            if (!topologia.layout_modo) topologia.layout_modo = 'raias';
            atualizarUILayout();
            renderizarCanvas();
            renderizarGrelha();
            renderizarOutliner();
            const modalEl = document.getElementById('modalAplicarTemplate');
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
        } else {
            const data = await resp.json();
            alert("Erro ao aplicar modelo: " + (data.error || "Tente novamente."));
        }
    } catch (e) {
        alert("Erro de conexão ao carregar modelo.");
    }
}
