import re

with open('auditoria/templates/auditoria/iso/fechamento_presentation.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the inner loop content for "Pontos Fortes"
pattern_c = re.compile(r'\{% for resp in grupos.conformidades %\}.*?\{% endfor %\}', re.DOTALL)
replacement_c = '''{% for dado in grupos.conformidades %}
            <div class="item-box border-start border-success border-5">
                <h4 class="text-success mb-3"><i class="bi bi-star-fill me-2"></i>Requisito {{ dado.item.referencia }} - {{ dado.item.titulo }}</h4>
                {% if dado.justificativa %}
                    <p class="mb-2 text-muted"><strong>Veredicto da Revisão:</strong> {{ dado.justificativa|linebreaksbr }}</p>
                {% else %}
                    <p class="mb-2 text-muted"><strong>Evidências:</strong></p>
                    <ul class="mb-0">
                    {% for resp in dado.respostas %}
                        {% if resp.texto_resposta %}<li>{{ resp.texto_resposta }}</li>{% endif %}
                    {% endfor %}
                    </ul>
                {% endif %}
            </div>
            {% endfor %}'''

content = pattern_c.sub(replacement_c, content)

# Replace for "Oportunidades"
pattern_om = re.compile(r'\{% for resp in grupos.oportunidades %\}.*?\{% endfor %\}', re.DOTALL)
replacement_om = '''{% for dado in grupos.oportunidades %}
            <div class="item-box border-start border-warning border-5">
                <h4 class="text-warning mb-3"><i class="bi bi-lightbulb-fill me-2"></i>Requisito {{ dado.item.referencia }} - {{ dado.item.titulo }}</h4>
                {% if dado.justificativa %}
                    <p class="mb-2 text-muted"><strong>Veredicto da Revisão:</strong> {{ dado.justificativa|linebreaksbr }}</p>
                {% else %}
                    <p class="mb-2 text-muted"><strong>Evidências:</strong></p>
                    <ul class="mb-0">
                    {% for resp in dado.respostas %}
                        {% if resp.texto_resposta %}<li>{{ resp.texto_resposta }}</li>{% endif %}
                    {% endfor %}
                    </ul>
                {% endif %}
            </div>
            {% endfor %}'''

content = pattern_om.sub(replacement_om, content)

# Replace for "NCs"
pattern_nc = re.compile(r'\{% for resp in grupos.nc_menores %\}.*?\{% endfor %\}', re.DOTALL)
replacement_nc = '''{% for dado in grupos.nc_menores %}
            <div class="item-box border-start border-danger border-5">
                <h4 class="text-danger mb-3"><i class="bi bi-exclamation-triangle-fill me-2"></i>Requisito {{ dado.item.referencia }} - {{ dado.item.titulo }}</h4>
                {% if dado.justificativa %}
                    <p class="mb-2 text-muted"><strong>Veredicto da Revisão:</strong> {{ dado.justificativa|linebreaksbr }}</p>
                {% else %}
                    <p class="mb-2 text-muted"><strong>Constatações:</strong></p>
                    <ul class="mb-0">
                    {% for resp in dado.respostas %}
                        {% if resp.classificacao == 'NC' %}
                            <li>{{ resp.texto_resposta|default:"Sem evidência descrita" }}</li>
                        {% endif %}
                    {% endfor %}
                    </ul>
                {% endif %}
            </div>
            {% endfor %}'''

content = pattern_nc.sub(replacement_nc, content)

with open('auditoria/templates/auditoria/iso/fechamento_presentation.html', 'w', encoding='utf-8') as f:
    f.write(content)
