"""Fix all misplaced 'from typing import Any' imports in the workspace."""
import glob

all_fixed = 0

for fp in sorted(glob.glob('packages/**/src/**/*.py', recursive=True)):
    with open(fp) as f:
        content = f.read()
    
    original = content
    lines = content.split('\n')
    changed = False
    
    # Remove ALL misplaced (indented) "from typing import Any" lines
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == 'from typing import Any' and line[0:1] in (' ', '\t'):
            changed = True
        else:
            new_lines.append(line)
    
    if not changed:
        continue
    
    lines = new_lines
    
    # Check if there's a module-level one now
    has_module = any(
        l.strip() == 'from typing import Any' and l[0:1] not in (' ', '\t')
        for l in lines if l.strip()
    )
    
    if not has_module:
        in_docstring = False
        insert_pos = 0
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith('"""') or s.startswith("'''"):
                in_docstring = not in_docstring
            if not in_docstring and (s.startswith('import ') or s.startswith('from ')):
                if not line.startswith((' ', '\t')):
                    insert_pos = i + 1
        
        if insert_pos > 0:
            lines.insert(insert_pos, 'from typing import Any')
        else:
            for i, line in enumerate(lines):
                s = line.strip()
                if not s:
                    insert_pos = i + 1
                elif not s.startswith('"""') and not s.startswith("'''") and not s.startswith('#'):
                    break
            lines.insert(insert_pos, 'from typing import Any')
    
    content = '\n'.join(lines)
    if content != original:
        with open(fp, 'w') as f:
            f.write(content)
        all_fixed += 1
        print(f'  ✓ {fp}')

print(f'\nFixed {all_fixed} files')
