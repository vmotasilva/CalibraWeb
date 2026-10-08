/* Editor de Diagramas (DOC.071) - módulo "persistencia"
 * Auto-save (com controle de concorrência) e histórico Desfazer/Refazer.
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

// =========================================================================
// AUTO-SAVE DE ALTA FREQUÊNCIA (DEBOUNCE 800ms)
// =========================================================================

// =========================================================================
// HISTÓRICO (DESFAZER / REFAZER) - snapshots da topologia, agrupados em janelas de 500 ms
// =========================================================================
const HISTORICO_MAX = 50;
let historicoUndo = [];
let historicoRedo = [];
let historicoBase = null;
let historicoTimer = null;

function iniciarHistorico() {
    historicoBase = JSON.stringify(topologia);
    atualizarBotoesHistorico();
}

function atualizarBotoesHistorico() {
    const u = document.getElementById('btnDesfazer');
    const r = document.getElementById('btnRefazer');
    if (u) u.disabled = historicoUndo.length === 0;
    if (r) r.disabled = historicoRedo.length === 0;
}

function registrarHistorico() {
    clearTimeout(historicoTimer);
    historicoTimer = null;
    if (historicoBase === null) return;
    const atual = JSON.stringify(topologia);
    if (atual === historicoBase) return;
    historicoUndo.push(historicoBase);
    if (historicoUndo.length > HISTORICO_MAX) historicoUndo.shift();
    historicoBase = atual;
    historicoRedo = [];
    atualizarBotoesHistorico();
}

function agendarHistorico() {
    clearTimeout(historicoTimer);
    historicoTimer = setTimeout(registrarHistorico, 500);
}

function restaurarSnapshot(snapshot) {
    topologia = JSON.parse(snapshot);
    if (!topologia.nodes) topologia.nodes = [];
    if (!topologia.edges) topologia.edges = [];
    if (!topologia.grid_data) topologia.grid_data = [];
    if (!topologia.estilo_linha) topologia.estilo_linha = 'ortogonal';
    historicoBase = JSON.stringify(topologia); // após normalizar, para a próxima comparação não gerar passo falso
    selectedNodeId = null;
    selectedNodeIds.clear();
    selectedEdgeId = null;
    if (!topologia.layout_modo) topologia.layout_modo = 'raias';
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    atualizarLabelEstiloLinha();
    atualizarUILayout();
    atualizarSelecoesVisuais();
    atualizarBotoesHistorico();
    dispararAutoSave();
}

function desfazer() {
    if (IS_APPROVED) return;
    registrarHistorico(); // fecha alterações pendentes antes de voltar
    if (historicoUndo.length === 0) return;
    historicoRedo.push(JSON.stringify(topologia));
    restaurarSnapshot(historicoUndo.pop());
}

function refazer() {
    if (IS_APPROVED) return;
    registrarHistorico();
    if (historicoRedo.length === 0) return;
    historicoUndo.push(JSON.stringify(topologia));
    restaurarSnapshot(historicoRedo.pop());
}

function dispararAutoSave() {
    if (IS_APPROVED || autoSaveConflito) return;
    agendarHistorico();

    const indicator = document.getElementById('saveIndicator');
    indicator.innerHTML = '<span class="text-warning"><i class="bi bi-arrow-repeat spin"></i> Salvando...</span>';

    if (autoSaveTimer) clearTimeout(autoSaveTimer);

    autoSaveTimer = setTimeout(async () => {
        try {
            const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/auto-save/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({ dados_topologia: topologia, base_atualizado_em: versaoAtualizadoEm })
            });

            if (resp.ok) {
                const resultado = await resp.json();
                if (resultado.atualizado_em) versaoAtualizadoEm = resultado.atualizado_em;
                indicator.innerHTML = '<span class="text-success"><i class="bi bi-check2-circle"></i> Sincronizado</span>';
            } else if (resp.status === 409) {
                autoSaveConflito = true;
                indicator.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-octagon-fill"></i> Conflito de edição</span>';
                alert("Este diagrama foi alterado em outra aba ou por outro usuário. Para não sobrescrever aquelas alterações, o salvamento foi pausado. Recarregue a página para continuar.");
            } else if (resp.status === 423) {
                indicator.innerHTML = '<span class="text-secondary"><i class="bi bi-lock-fill"></i> Bloqueado (Aprovado)</span>';
            } else {
                indicator.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-triangle"></i> Erro ao salvar</span>';
            }
        } catch (err) {
            indicator.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-triangle"></i> Erro de rede</span>';
        }
    }, 800);
}
