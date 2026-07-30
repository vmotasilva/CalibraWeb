import re

def update_file(filepath):
    print(f"Processing {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # We will use regex to find the blocks.
    # A block starts with <li><h6 class="dropdown-header text-muted">TITLE</h6></li>
    # and we want to replace it. But we also need to close the </ul> after the items.
    
    # Since we can't reliably know where the block ends without a real HTML parser,
    # and since we want to keep it simple, let's just do multi-line regex replacements.
    
    # Let's write a simple state machine parser.
    lines = content.split('\n')
    new_lines = []
    
    in_group = False
    group_indent = ""
    
    for line in lines:
        match = re.search(r'^(\s*)<li><h6 class="dropdown-header text-muted">(.*?)</h6></li>', line)
        if match:
            if in_group:
                # Close previous group if it wasn't closed properly
                new_lines.append(f'{group_indent}    </ul>')
                new_lines.append(f'{group_indent}</li>')
                in_group = False
                
            group_indent = match.group(1)
            title = match.group(2).strip()
            slug = re.sub(r'[^a-zA-Z0-9]', '', title)
            
            new_lines.append(f'{group_indent}<li>')
            new_lines.append(f'{group_indent}    <h6 class="dropdown-header text-muted d-flex justify-content-between align-items-center" data-bs-toggle="collapse" data-bs-target="#collapse{slug}" style="cursor: pointer;">')
            new_lines.append(f'{group_indent}        {title} <i class="bi bi-chevron-down transition-transform rotate-180"></i>')
            new_lines.append(f'{group_indent}    </h6>')
            new_lines.append(f'{group_indent}    <ul class="list-unstyled collapse show" id="collapse{slug}">')
            
            in_group = True
            continue
            
        if in_group:
            # Check if this line is a dropdown divider or closing ul
            if '<li><hr class="dropdown-divider"></li>' in line or '</ul>' in line:
                new_lines.append(f'{group_indent}    </ul>')
                new_lines.append(f'{group_indent}</li>')
                new_lines.append(line)
                in_group = False
                continue
                
            # If we hit an {% endif %} that matches the group's indentation, it's likely closing the block
            # For example, if group_indent is 32 spaces, and this {% endif %} is 28 spaces, it's closing the outer if.
            # We must close our group BEFORE this line.
            indent_match = re.match(r'^(\s*){%\s*endif', line)
            if indent_match:
                if len(indent_match.group(1)) < len(group_indent):
                    new_lines.append(f'{group_indent}    </ul>')
                    new_lines.append(f'{group_indent}</li>')
                    new_lines.append(line)
                    in_group = False
                    continue
                    
        new_lines.append(line)
        
    if in_group:
        new_lines.append(f'{group_indent}    </ul>')
        new_lines.append(f'{group_indent}</li>')
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

update_file('shared/templates/base_desktop.html')
update_file('shared/templates/base_mobile.html')
