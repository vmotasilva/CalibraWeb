import json
with open('iso13485_secoes_4_a_8.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    for item in data:
        if item['referencia'].startswith('5'):
            print(f"{item['referencia']} - is_parent: {item.get('is_parent', 'N/A')}")
