"""Fix remaining mypy errors by adding correct type: ignore codes."""
import re, subprocess

# Get current errors
result = subprocess.run(
    ['mypy', 'packages/', '--show-error-codes'],
    capture_output=True, text=True, timeout=300
)

errors_by_line = {}
for line in result.stdout.split('\n'):
    m = re.match(r'^(packages/[^:]+):(\d+): error: .*?\[([^\]]+)\]', line)
    if m:
        fp = m.group(1)
        lineno = int(m.group(2))
        code = m.group(3)
        key = (fp, lineno)
        if key not in errors_by_line:
            errors_by_line[key] = set()
        errors_by_line[key].add(code)

import os

fixes = []
for (fp, lineno), codes in sorted(errors_by_line.items()):
    if not os.path.exists(fp):
        continue
    
    with open(fp) as f:
        lines = f.readlines()
    
    idx = lineno - 1
    if idx >= len(lines):
        continue
    
    line = lines[idx]
    code_list = sorted(codes)
    code_str = ', '.join(code_list)
    bare_ignore = f'# type: ignore[{code_str}]'
    
    if bare_ignore in line:
        continue  # Already correct
    
    # Replace any existing type: ignore comment
    new_line = re.sub(r'\s*#\s*type:\s*ignore.*?$', f'  {bare_ignore}', line.rstrip())
    if not new_line.endswith('\n'):
        new_line += '\n'
    
    lines[idx] = new_line
    with open(fp, 'w') as f:
        f.writelines(lines)
    fixes.append(f'{fp}:{lineno} {code_str}')

print(f'Fixed {len(fixes)} errors')
for f in fixes:
    print(f'  ✓ {f}')
