"""Fix all remaining broken type: ignore lines — split merged lines, fix codes."""
import re

# These files have merge issues — two lines became one
merged_files = {
    'packages/ontoderive/src/ontoderive/fault_tolerance_policy.py': [
        # original 2 lines: BOSEvent = None ... EventType = None ... 
        (r"( +)(BOSEvent = None  # type: ignore\[[^\]]+\])(\s+)(EventType = None.*?\n)", 
         lambda m: m.group(1) + m.group(2) + '\n' + m.group(1) + m.group(4)),
    ],
    'packages/ontoderive/src/ontoderive/document.py': [
        (r"( +)(BOSEvent = None  # type: ignore\[[^\]]+\])(\s+)(EventType = None.*?\n)",
         lambda m: m.group(1) + m.group(2) + '\n' + m.group(1) + m.group(4)),
    ],
    'packages/ontoderive/engine/fault_tolerance_policy.py': [
        (r"( +)(BOSEvent = None  # type: ignore\[[^\]]+\])(\s+)(EventType = None.*?\n)",
         lambda m: m.group(1) + m.group(2) + '\n' + m.group(1) + m.group(4)),
    ],
    'packages/ontoderive/engine/document.py': [
        (r"( +)(BOSEvent = None  # type: ignore\[[^\]]+\])(\s+)(EventType = None.*?\n)",
         lambda m: m.group(1) + m.group(2) + '\n' + m.group(1) + m.group(4)),
    ],
    'packages/agora/src/agora/edge_computing.py': [
        (r"( +)(updates = .*?  # type: ignore\[[^\]]+\])(\s+)(\w.*?)(\n)",
         lambda m: m.group(1) + m.group(2) + '\n' + m.group(1) + m.group(4) + m.group(5)),
    ],
}

import os

for fp, patterns in merged_files.items():
    if not os.path.exists(fp):
        print(f'SKIP: {fp}')
        continue
    
    with open(fp) as f:
        content = f.read()
    
    original = content
    for pattern, replacer in patterns:
        content = re.sub(pattern, replacer, content)
    
    if content != original:
        with open(fp, 'w') as f:
            f.write(content)
        print(f'FIXED: {fp}')
    else:
        print(f'NO CHANGE: {fp}')
