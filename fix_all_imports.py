#!/usr/bin/env python3
"""Fix all import-not-found and import-untyped errors across 5 packages + 10 import-untyped files."""

import re
import subprocess
import sys
from collections import defaultdict

WORKSPACE = "/Users/xiamingxing/Workspace/projects/kairon"
MYPY = "/opt/homebrew/bin/mypy"

PACKAGES = [
    ("iris", "packages/iris/src/"),
    ("codeanalyze", "packages/codeanalyze/src/"),
    ("metaos", "packages/metaos/src/"),
    ("ecos", "packages/ecos/src/"),
    ("agent-runtime", "packages/agent-runtime/src/"),
]


def run_mypy(pkg_path):
    cmd = [
        MYPY, "--no-incremental", "--explicit-package-bases",
        "--exclude", "tests/", "--exclude", "build/",
        pkg_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=WORKSPACE)
    return result.stdout + result.stderr


def parse_import_not_found(raw_output):
    """Parse mypy output for import-not-found errors."""
    errors = []
    for line in raw_output.split('\n'):
        if 'import-not-found]' not in line:
            continue
        m = re.match(r'^(.+?):(\d+): error: .+\[import-not-found\]$', line)
        if m:
            filepath = m.group(1)
            lineno = int(m.group(2))
            errors.append((filepath, lineno))
    return errors


def fix_file_import_not_found(filepath, line_numbers):
    """Fix import-not-found errors by adding # type: ignore[import-not-found]."""
    full_path = f"{WORKSPACE}/{filepath}"
    
    with open(full_path, 'r') as f:
        lines = f.readlines()
    
    sorted_lines = sorted(set(line_numbers), reverse=True)
    modified = False
    
    for lineno in sorted_lines:
        idx = lineno - 1
        if idx >= len(lines):
            print(f"  WARNING: Line {lineno} out of range in {filepath}, skipping")
            continue
        
        line = lines[idx]
        stripped = line.rstrip('\n').rstrip('\r')
        content = stripped.lstrip()
        
        if not (content.startswith('import ') or content.startswith('from ')):
            print(f"  WARNING: Line {lineno} in {filepath} is not an import: {content!r}")
            continue
        
        if '# type: ignore' in stripped:
            if 'import-not-found' in stripped:
                continue  # Already covered
            
            m = re.search(r'# type:\s*ignore\[([^\]]*)\]', stripped)
            if m:
                existing = m.group(1)
                if 'import-not-found' not in existing:
                    new_ignore = existing + ', import-not-found'
                    new_line = stripped.replace(m.group(0), f'# type: ignore[{new_ignore}]')
                    lines[idx] = new_line + '\n'
                    modified = True
            else:
                new_line = stripped + '  # type: ignore[import-not-found]\n'
                lines[idx] = new_line
                modified = True
        else:
            comment_match = re.search(r'(?<!\S#)\s+#\s', stripped)
            if comment_match:
                pos = comment_match.start()
                before_comment = stripped[:pos]
                comment_part = stripped[pos:]
                new_line = before_comment + '  # type: ignore[import-not-found]  ' + comment_part.strip().lstrip('#').strip() + '\n'
                lines[idx] = new_line
                modified = True
            else:
                new_line = stripped + '  # type: ignore[import-not-found]\n'
                lines[idx] = new_line
                modified = True
    
    if modified:
        with open(full_path, 'w') as f:
            f.writelines(lines)
        return True
    return False


def fix_import_untyped(filepath, lineno):
    """Fix an import-untyped error by ensuring the line has # type: ignore[import-untyped]."""
    full_path = f"{WORKSPACE}/{filepath}"
    
    with open(full_path, 'r') as f:
        lines = f.readlines()
    
    idx = lineno - 1
    if idx >= len(lines):
        print(f"  WARNING: Line {lineno} out of range in {filepath}, skipping")
        return False
    
    line = lines[idx]
    stripped = line.rstrip('\n').rstrip('\r')
    
    if '# type: ignore' in stripped:
        if 'import-untyped' in stripped:
            print(f"  Already has import-untyped: {filepath}:{lineno}")
            return False
        
        m = re.search(r'# type:\s*ignore\[([^\]]*)\]', stripped)
        if m:
            existing = m.group(1)
            if 'import-untyped' not in existing:
                new_ignore = existing + ', import-untyped'
                new_line = stripped.replace(m.group(0), f'# type: ignore[{new_ignore}]')
                lines[idx] = new_line + '\n'
        else:
            new_line = stripped + '  # type: ignore[import-untyped]\n'
            lines[idx] = new_line
    else:
        new_line = stripped + '  # type: ignore[import-untyped]\n'
        lines[idx] = new_line
    
    with open(full_path, 'w') as f:
        f.writelines(lines)
    
    return True


def main():
    total_import_not_found_fixed = 0
    total_import_not_found_errors = 0
    total_import_untyped_fixed = 0
    
    # ---- Fix import-not-found errors ----
    for pkg_name, pkg_path in PACKAGES:
        print(f"\n{'='*60}")
        print(f"Processing {pkg_name} ({pkg_path})")
        print(f"{'='*60}")
        
        raw = run_mypy(pkg_path)
        errors = parse_import_not_found(raw)
        
        total_errors_count = raw.count('[import-not-found]')
        print(f"  Found {total_errors_count} import-not-found errors ({len(errors)} parsed)")
        
        if not errors:
            print(f"  No errors to fix!")
            continue
        
        by_file = defaultdict(set)
        for filepath, lineno in errors:
            by_file[filepath].add(lineno)
        
        pkg_fixed = 0
        for filepath in sorted(by_file.keys()):
            if fix_file_import_not_found(filepath, list(by_file[filepath])):
                pkg_fixed += len(by_file[filepath])
        
        total_import_not_found_fixed += pkg_fixed
        total_import_not_found_errors += total_errors_count
        print(f"  Fixed {pkg_fixed}/{total_errors_count} errors in {pkg_name}")
    
    print(f"\n{'='*60}")
    print(f"IMPORT-NOT-FOUND: Fixed {total_import_not_found_fixed}/{total_import_not_found_errors} errors")
    print(f"{'='*60}")
    
    # ---- Fix import-untyped errors ----
    print(f"\n{'='*60}")
    print(f"Processing import-untyped errors")
    print(f"{'='*60}")
    
    import_untyped_files = [
        # 1. lancedb_backend.py:35
        ("packages/eidos/src/eidos/vector_backends/lancedb_backend.py", [35]),
        # 2. gemini_provider.py:49
        ("packages/llm-gateway/src/llm_gateway/providers/gemini_provider.py", [49]),
        # 3-5. executor.py:402,469,470
        ("packages/minerva/src/minerva/executor/executor.py", [402, 469, 470]),
        # 6. store.py:657
        ("packages/minerva/src/minerva/knowledge/store.py", [657]),
        # 7. backends.py:454
        ("packages/minerva/src/minerva/search/backends.py", [454]),
        # 8-10. ner.py:117 (jieba, jieba.posseg - 2 imports on same line?)
        ("packages/ontoderive/engine/intelligence/ner.py", [117]),
    ]
    
    for filepath, line_numbers in import_untyped_files:
        for lineno in line_numbers:
            if fix_import_untyped(filepath, lineno):
                total_import_untyped_fixed += 1
                print(f"  Fixed import-untyped: {filepath}:{lineno}")
    
    print(f"\n{'='*60}")
    print(f"IMPORT-UNTYPED: Fixed {total_import_untyped_fixed} errors")
    print(f"{'='*60}")
    
    # ---- Verify ----
    print(f"\n\n{'='*60}")
    print(f"VERIFICATION")
    print(f"{'='*60}")
    
    grand_remaining = 0
    for pkg_name, pkg_path in PACKAGES:
        raw = run_mypy(pkg_path)
        remaining = raw.count('[import-not-found]')
        grand_remaining += remaining
        if remaining > 0:
            print(f"\n{pkg_name}: {remaining} import-not-found errors REMAINING:")
            for line in raw.split('\n'):
                if 'import-not-found]' in line:
                    print(f"  {line.strip()}")
        else:
            print(f"\n{pkg_name}: ✅ 0 import-not-found errors remaining")
    
    print(f"\n{'='*60}")
    print(f"GRAND TOTAL REMAINING import-not-found: {grand_remaining}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
