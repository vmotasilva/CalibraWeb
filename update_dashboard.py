import re

with open(r'metrologia\templates\metrologia\dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Change modal-lg to modal-xl
content = content.replace('modal-dialog modal-dialog-centered modal-lg', 'modal-dialog modal-dialog-centered modal-xl')

# 2. Add data-ocorrencia logic to the row
content = content.replace('data-periodo=\"{% if i.data_proxima_calibracao %}{{ i.data_proxima_calibracao|date:\'Y-m\' }}{% endif %}\"', 'data-periodo=\"{% if i.data_proxima_calibracao %}{{ i.data_proxima_calibracao|date:\'Y-m\' }}{% endif %}\"\n                            data-ocorrencia=\"{% if i.ocorrencias.all %}{% for oc in i.ocorrencias.all %}{% if oc.status == \'ABERTA\' %}COM_ABERTA{% endif %}{% endfor %}{% endif %}\"')

# 3. Update JS logic
content = content.replace('const filtrosAtivos = { status: [], situacao: [], categoria: [], setor: [], resultado: [], acao: [], periodo: [] };', 'const filtrosAtivos = { status: [], situacao: [], categoria: [], setor: [], resultado: [], acao: [], periodo: [], ocorrencia: [] };')
js_replacement = '''if (mostrar && filtrosAtivos.periodo.length > 0 && !filtrosAtivos.periodo.includes(row.dataset.periodo)) mostrar = false;
        if (mostrar && filtrosAtivos.ocorrencia.length > 0) {
            if (filtrosAtivos.ocorrencia.includes("COM_ABERTA") && !row.dataset.ocorrencia.includes("COM_ABERTA")) mostrar = false;
        }'''
content = content.replace('if (mostrar && filtrosAtivos.periodo.length > 0 && !filtrosAtivos.periodo.includes(row.dataset.periodo)) mostrar = false;', js_replacement)

# 4. Extract the filter row contents (everything between <div class=\"row\"> and its closing div before </div>\n                    </div>\n                    <div class=\"modal-footer)
match = re.search(r'(<div class=\"sidebar-scroll\">\s*<div class=\"row\">)(.*?)(</div>\s*</div>\s*</div>\s*<div class=\"modal-footer bg-light)', content, re.DOTALL)
if match:
    new_cols = '''
                    <!-- Coluna 1 -->
                    <div class="col-md-3">
                        <!-- 1. SITUAÇÃO (Vencimento) -->
                        <div class="filter-group open mb-3">
                            <div class="filter-header" onclick="toggleFilterGroup(this)">
                                <label class="form-label small fw-bold text-muted mb-0">SITUAÇÃO</label>
                                <i class="bi bi-chevron-down"></i>
                            </div>
                            <div class="filter-content">
                                <button class="btn btn-xs btn-link p-0 mb-2 small" onclick="selectAllInCategory('situacao')">Selecionar Todos</button>
                                <div class="d-flex flex-column gap-1">
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="VENCIDO" data-category="situacao">
                                        <label class="form-check-label small text-danger fw-bold">Vencidos</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="AVENCER_30" data-category="situacao">
                                        <label class="form-check-label small text-warning fw-bold">A Vencer (30 dias)</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="AVENCER_60" data-category="situacao">
                                        <label class="form-check-label small text-warning">A Vencer (60 dias)</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="AVENCER_90" data-category="situacao">
                                        <label class="form-check-label small text-warning">A Vencer (90 dias)</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="AVENCER_120" data-category="situacao">
                                        <label class="form-check-label small text-warning">A Vencer (120 dias)</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="EM_DIA" data-category="situacao">
                                        <label class="form-check-label small text-success">Em Dia</label>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- 2. STATUS (Ativo/Inativo) -->
                        <div class="filter-group open mb-3">
                            <div class="filter-header" onclick="toggleFilterGroup(this)">
                                <label class="form-label small fw-bold text-muted mb-0">STATUS</label>
                                <i class="bi bi-chevron-down"></i>
                            </div>
                            <div class="filter-content">
                                <button class="btn btn-xs btn-link p-0 mb-2 small" onclick="selectAllInCategory('status')">Selecionar Todos</button>
                                <div class="d-flex flex-column gap-1">
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="ATIVO" id="st_ativo" data-category="status" checked>
                                        <label class="form-check-label small">Ativos</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="INATIVO" data-category="status">
                                        <label class="form-check-label small">Inativos / Descontinuados</label>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Coluna 2 -->
                    <div class="col-md-3">
                        <!-- 7. PERÍODO (Próxima Calibração) -->
                        <div class="filter-group open mb-3">
                            <div class="filter-header" onclick="toggleFilterGroup(this)">
                                <label class="form-label small fw-bold text-muted mb-0">PRÓX. CALIBRAÇÃO</label>
                                <i class="bi bi-chevron-down"></i>
                            </div>
                            <div class="filter-content">
                                <button class="btn btn-xs btn-link p-0 mb-2 small" onclick="selectAllInCategory('periodo')">Selecionar Todos</button>
                                <div class="d-flex flex-column gap-1" style="max-height: 180px; overflow-y: auto;">
                                    {% for p in periodos_filtro %}
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="{{ p.value }}" data-category="periodo">
                                        <label class="form-check-label small">{{ p.label }}</label>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>

                        <!-- 3. AÇÃO -->
                        <div class="filter-group open mb-3">
                            <div class="filter-header" onclick="toggleFilterGroup(this)">
                                <label class="form-label small fw-bold text-muted mb-0">AÇÃO</label>
                                <i class="bi bi-chevron-down"></i>
                            </div>
                            <div class="filter-content">
                                <button class="btn btn-xs btn-link p-0 mb-2 small" onclick="selectAllInCategory('acao')">Selecionar Todos</button>
                                <div class="d-flex flex-column gap-1">
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="CALIBRACAO" data-category="acao">
                                        <label class="form-check-label small">Calibração</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="VERIFICACAO" data-category="acao">
                                        <label class="form-check-label small">Verificação</label>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Coluna 3 -->
                    <div class="col-md-3">
                        <!-- 4. CATEGORIA -->
                        <div class="filter-group open mb-3">
                            <div class="filter-header" onclick="toggleFilterGroup(this)">
                                <label class="form-label small fw-bold text-muted mb-0">CATEGORIA</label>
                                <i class="bi bi-chevron-down"></i>
                            </div>
                            <div class="filter-content">
                                <button class="btn btn-xs btn-link p-0 mb-2 small" onclick="selectAllInCategory('categoria')">Selecionar Todos</button>
                                <div class="d-flex flex-column gap-1" style="max-height: 180px; overflow-y: auto;">
                                    {% for cat in categorias_filtro %}
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="{{ cat.id }}" data-category="categoria">
                                        <label class="form-check-label small">{{ cat.nome }}</label>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>

                        <!-- 5. SETOR -->
                        <div class="filter-group open mb-3">
                            <div class="filter-header" onclick="toggleFilterGroup(this)">
                                <label class="form-label small fw-bold text-muted mb-0">SETOR</label>
                                <i class="bi bi-chevron-down"></i>
                            </div>
                            <div class="filter-content">
                                <button class="btn btn-xs btn-link p-0 mb-2 small" onclick="selectAllInCategory('setor')">Selecionar Todos</button>
                                <div class="d-flex flex-column gap-1" style="max-height: 180px; overflow-y: auto;">
                                    {% for s in setores_filtro %}
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="{{ s.id }}" data-category="setor">
                                        <label class="form-check-label small">{{ s.nome }}</label>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Coluna 4 -->
                    <div class="col-md-3">
                        <!-- 6. RESULTADO -->
                        <div class="filter-group open mb-3">
                            <div class="filter-header" onclick="toggleFilterGroup(this)">
                                <label class="form-label small fw-bold text-muted mb-0">RESULTADO</label>
                                <i class="bi bi-chevron-down"></i>
                            </div>
                            <div class="filter-content">
                                <button class="btn btn-xs btn-link p-0 mb-2 small" onclick="selectAllInCategory('resultado')">Selecionar Todos</button>
                                <div class="d-flex flex-column gap-1">
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="APROVADO_SEM_CORRECAO" data-category="resultado">
                                        <label class="form-check-label small">Aprovado</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="APROVADO_COM_CORRECAO" data-category="resultado">
                                        <label class="form-check-label small">Aprv. c/ Correção</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="REPROVADO" data-category="resultado">
                                        <label class="form-check-label small">Reprovado</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="SEM_CALIBRACAO" data-category="resultado">
                                        <label class="form-check-label small">Sem Calibração</label>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- 8. OCORRÊNCIA -->
                        <div class="filter-group open mb-3">
                            <div class="filter-header" onclick="toggleFilterGroup(this)">
                                <label class="form-label small fw-bold text-muted mb-0">OCORRÊNCIA</label>
                                <i class="bi bi-chevron-down"></i>
                            </div>
                            <div class="filter-content">
                                <div class="d-flex flex-column gap-1">
                                    <div class="form-check">
                                        <input class="form-check-input filter-checkbox" type="checkbox" value="COM_ABERTA" data-category="ocorrencia">
                                        <label class="form-check-label small text-danger fw-bold">Com Ocorrência Aberta</label>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
'''
    content = content[:match.start(2)] + '\n' + new_cols + '\n' + content[match.end(2):]

with open(r'metrologia\templates\metrologia\dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated successfully")
