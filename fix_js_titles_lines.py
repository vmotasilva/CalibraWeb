with open('boards/templates/boards/board_detail.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'title: "{% if card.data_conclusao %}' in line:
        lines[i] = '                            title: "{% if card.data_conclusao %}[Concluído] {% elif card.data_entrega and card.data_entrega < hoje %}[Atrasado] {% else %}{% endif %}{% if card.prioridade == \'ALTA\' %}[ALTA] {% endif %}{{ card.titulo|escapejs }}",\n'

with open('boards/templates/boards/board_detail.html', 'w', encoding='utf-8') as f:
    f.writelines(lines)
