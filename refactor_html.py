import re

with open('auditoria/templates/auditoria/iso/revisao_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

new_html = '''
    <div class="accordion" id="accordionBlocos">
        {% for bloco in blocos %}
        <div class="accordion-item mb-2 border rounded shadow-sm item-card" data-status="{{ bloco.pior_status }}">
            <h2 class="accordion-header" id="heading{{ bloco.item.id }}">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse{{ bloco.item.id }}" aria-expanded="false" aria-controls="collapse{{ bloco.item.id }}">
                    <div class="d-flex w-100 justify-content-between align-items-center me-3">
                        <div>
                            <strong>Item {{ bloco.item.referencia }}</strong> - {{ bloco.item.titulo }}
                        </div>
                        <div class="status-badge-container" id="badgeContainer{{ bloco.item.id }}">
                            {% if bloco.pior_status == 'NC' %}
                                <span class="badge bg-danger fs-6">Não Conforme</span>
                            {% elif bloco.pior_status == 'OM' %}
                                <span class="badge bg-warning text-dark fs-6">OM</span>
                            {% elif bloco.pior_status == 'C' %}
                                <span class="badge bg-success fs-6">Conforme</span>
                            {% else %}
                                <span class="badge bg-secondary fs-6">Pendente</span>
                            {% endif %}
                        </div>
                    </div>
                </button>
            </h2>
            <div id="collapse{{ bloco.item.id }}" class="accordion-collapse collapse" aria-labelledby="heading{{ bloco.item.id }}" data-bs-parent="#accordionBlocos">
                <div class="accordion-body bg-light">
                    <div class="mb-4">
                        <h6 class="fw-bold text-secondary"><i class="bi bi-card-text me-2"></i>Requisito da Norma:</h6>
                        <div class="p-3 bg-white border rounded text-muted">
                            {{ bloco.item.descricao|default:"<em>Sem descrição registrada.</em>"|linebreaksbr }}
                        </div>
                    </div>
                    
                    <h6 class="fw-bold text-primary mb-3"><i class="bi bi-search me-2"></i>Constatações / Evidências de Auditoria:</h6>
                    
                    {% for resp in bloco.respostas %}
                    <div class="mb-3 p-3 bg-white border rounded shadow-sm">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="badge {% if resp.classificacao == 'NC' %}bg-danger{% elif resp.classificacao == 'OM' %}bg-warning text-dark{% elif resp.classificacao == 'C' %}bg-success{% else %}bg-secondary{% endif %}">Status Origem: {{ resp.get_classificacao_display }}</span>
                            <div>
                                <span class="text-muted small">Avaliado em:</span>
                                {% for agenda in resp.agendas_avaliadas %}
                                    <span class="badge bg-light text-dark border ms-1"><i class="bi bi-geo-alt me-1"></i>{{ agenda.titulo|default:"Geral" }}</span>
                                {% empty %}
                                    <span class="badge bg-light text-dark border ms-1">Global</span>
                                {% endfor %}
                            </div>
                        </div>
                        <p class="mb-2 small text-muted"><strong>Pergunta Base:</strong> {{ resp.pergunta.texto_pergunta }}</p>
                        <div class="p-2 bg-light border rounded">
                            {{ resp.texto_resposta|default:"<em>Nenhuma anotação registrada.</em>"|linebreaksbr }}
                        </div>
                        
                        {% if resp.solicitacoes.all %}
                        <div class="mt-2">
                            <span class="text-warning small fw-bold"><i class="bi bi-pin-angle-fill me-1"></i>Solicitações associadas:</span>
                            <ul class="list-unstyled ms-3 mt-1 small">
                                {% for sol in resp.solicitacoes.all %}
                                <li>- {{ sol.solicitacao }}</li>
                                {% endfor %}
                            </ul>
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}

                    <div class="mt-4 p-3 border rounded bg-white border-info">
                        <h6 class="fw-bold text-info"><i class="bi bi-chat-left-text me-2"></i>Veredicto Final do Requisito (Direito de Resposta)</h6>
                        <div class="mb-3">
                            <label for="argumentacao_{{ bloco.item.id }}" class="form-label text-muted small">Argumentação ou Nova Evidência (Justificativa):</label>
                            <textarea class="form-control" id="argumentacao_{{ bloco.item.id }}" rows="3" placeholder="Descreva aqui a argumentação da reavaliação global do requisito..."></textarea>
                        </div>
                        <div class="d-flex gap-2">
                            <button type="button" class="btn btn-warning" onclick="reverterStatus({{ bloco.item.id }}, 'OM')">
                                <i class="bi bi-arrow-repeat"></i> Definir como OM
                            </button>
                            <button type="button" class="btn btn-success" onclick="reverterStatus({{ bloco.item.id }}, 'C')">
                                <i class="bi bi-check-circle-fill"></i> Definir como Conforme
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        {% empty %}
        <div class="alert alert-info">Não há respostas para revisar nesta auditoria ainda.</div>
        {% endfor %}
    </div>
'''

pattern = re.compile(r'{% for bloco in blocos %}\s*<div class="mb-5 bloco-container">.*?{% endfor %}\s*</div>', re.DOTALL)
new_content = pattern.sub(new_html, content)

# update the script JS as well
new_content = new_content.replace('function reverterStatus(respostaId, novoStatus) {', 'function reverterStatus(itemNormaId, novoStatus) {')
new_content = new_content.replace("argumentacao_' + respostaId", "argumentacao_' + itemNormaId")
new_content = new_content.replace('resposta_id: respostaId', 'item_norma_id: itemNormaId,\n                auditoria_id: {{ auditoria.id }}')
new_content = new_content.replace('heading${respostaId}', 'heading${itemNormaId}')
new_content = new_content.replace('badgeContainer_\' + respostaId', 'badgeContainer_\' + itemNormaId')
new_content = new_content.replace('badgeContainer\' + respostaId', 'badgeContainer\' + itemNormaId')
new_content = new_content.replace('collapse\' + respostaId', 'collapse\' + itemNormaId')

with open('auditoria/templates/auditoria/iso/revisao_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(new_content)
