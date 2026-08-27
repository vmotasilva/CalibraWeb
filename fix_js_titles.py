import re
with open('boards/templates/boards/board_detail.html', 'r', encoding='utf-8') as f:
    content = f.read()
    
# Find the specific title lines and replace them
pattern = r'title: "\{% if card.data_conclusao %\}.*?\{% elif card.data_entrega and card.data_entrega < hoje %\}.*?\{% else %\}.*?\{% endif %\}\{% if card.prioridade == ''ALTA'' %\}.*?\{% endif %\}\{\{ card.titulo\|escapejs \}\}",'
replacement = 'title: "{% if card.data_conclusao %}[Concluído] {% elif card.data_entrega and card.data_entrega < hoje %}[Atrasado] {% else %}{% endif %}{% if card.prioridade == \'ALTA\' %}[ALTA] {% endif %}{{ card.titulo|escapejs }}",'

new_content = re.sub(pattern, replacement, content)

with open('boards/templates/boards/board_detail.html', 'w', encoding='utf-8') as f:
    f.write(new_content)
