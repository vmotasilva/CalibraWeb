import sys
with open('metrologia/templates/metrologia/dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()
with open('replacement.txt', 'r', encoding='utf-8') as f:
    replacement = f.read()

start_marker = '<!-- keep sidebar-col open so sidebar-scroll stays inside -->'
end_marker = '<div class="modal-footer bg-light"'

start_idx = html.find(start_marker)
end_idx = html.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print('Markers not found', start_idx, end_idx)
    sys.exit(1)

# Find the end of the divs before modal-footer
# We want to replace everything between start_marker and end_marker except the closing divs that might be there.
# Looking at dashboard.html:
# 312:                     </div>
# 313:                     </div>
# 314:                     <div class="modal-footer bg-light"
# The replacement text already includes the closing divs if I didn't remove them? No, replacement.txt ends with </div></div></div>
# Let's just find exactly what's there and replace.
# Actually I will just find the start of <!-- keep sidebar... --> and end before <!-- Busca e ações... 
# Wait, no. end_marker is right.

# Let's just use regular replace since we know the exact boundaries
new_html = html[:start_idx] + replacement + '\n                    ' + html[end_idx:]
with open('metrologia/templates/metrologia/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
print('Replaced successfully')