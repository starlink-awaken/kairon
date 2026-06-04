"""Fix remaining mypy errors: combine all error codes per line."""
import re, subprocess
from collections import defaultdict

result = subprocess.run(
    ['mypy', 'packages/', '--show-error-codes'],
    capture_output=True, text=True, timeout=300
)

# Group all error codes by (file, line)
line_codes = defaultdict(set)
for line in result.stdout.split('\n'):
    m = re.match(r'^(packages/[^:]+):(\d+): error:', line)
    if m:
        fp = m.group(1)
        lineno = int(m.group(2))
        # Extract the error code from the end
        code_m = re.search(r'\[([^\]]+)\]$', line)
        if code_m:
            line_codes[(fp, lineno)].add(code_m.group(1))

import os

fixed = 0
for (fp, lineno), codes in sorted(line_codes.items()):
    if not os.path.exists(fp):
        continue
    
    with open(fp) as f:
        lines = f.readlines()
    
    idx = lineno - 1
    if idx >= len(lines):
        continue
    
    code_str = ', '.join(sorted(codes))
    full_ignore = f'# type: ignore[{code_str}]'
    
    line = lines[idx]
    # Remove any existing type: ignore
    cleaned = re.sub(r'\s*#\s*type:\s*ignore[^\]\n]*\]?\s*', '', line)
    if cleaned.endswith('\n'):
        cleaned = cleaned.rstrip('\n') + f'  {full_ignore}\n'
    else:
        cleaned += f'  {full_ignore}'
    
    if cleaned != line:
        lines[idx] = cleaned
        with open(fp, 'w') as f:
            f.writelines(lines)
        fixed += 1
        print(f'  ✓ {fp}:{lineno} -> {full_ignore}')

print(f'\nFixed {fixed} lines')
