#!/usr/bin/env python
# Script para reorganizar o template

with open('metrologia/templates/metrologia/editar_historico.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Extract PDF+carimbo content (lines 160-459, 0-indexed: 159-459)
pdf_content = lines[159:459]

# Remove those lines from original position
new_lines = lines[:159] + lines[459:]

# Find the position to insert (after "<!-- COLUNA 2: PRÉ-VISUALIZAÇÃO + CARIMBO (Direita) -->" and "<div class="col-lg-6">")
insert_pos = None
for i, line in enumerate(new_lines):
    if 'COLUNA 2: PRÉ-VISUALIZAÇÃO + CARIMBO' in line and 'Direita' in line:
        # Found the comment, insert 2 lines after (after opening <div>)
        insert_pos = i + 2
        break

if insert_pos:
    print(f'Found coluna 2 at line {insert_pos}')
    new_lines = new_lines[:insert_pos] + pdf_content + new_lines[insert_pos:]
    
    with open('metrologia/templates/metrologia/editar_historico.html', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('File reorganized successfully!')
else:
    print('ERROR: Could not find coluna 2')
