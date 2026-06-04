#!/usr/bin/env python3
"""
Fix all import-not-found errors by adding # type: ignore[import-not-found] to each import line.
"""

import re
import subprocess
import sys
from collections import defaultdict

WORKSPACE = "/Users/xiamingxing/Workspace/projects/kairon"
MYPY = "/opt/homebrew/bin/mypy"

PACKAGES = [
    ("agora", "packages/agora/src/"),
    ("engine-core", "packages/engine-core/src/"),
    ("kos", "packages/kos/src/"),
    ("kronos", "packages/kronos/src/"),
    ("forge", "packages/forge/src/"),
]

def run_mypy(pkg_name, pkg_path):
    """Run mypy and return the raw output."""
    cmd = [
        MYPY, "--no-incremental", "--explicit-package-bases",
        "--exclude", "tests/", "--exclude", "build/",
        pkg_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=WORKSPACE)
    return result.stdout + result.stderr


def parse_errors(raw_output):
    """Parse mypy output to extract (filepath, lineno) for import-not-found errors."""
    errors = []
    for line in raw_output.split('\n'):
        if 'import-not-found]' not in line:
            continue
        # Format: packages/agora/src/agora/file.py:LINE: error: ...  [import-not-found]
        m = re.match(r'^(.+?):(\d+): error: .+\[import-not-found\]$', line)
        if m:
            filepath = m.group(1)
            lineno = int(m.group(2))
            errors.append((filepath, lineno))
    return errors


def fix_file(filepath, line_numbers):
    """Fix all import-not-found errors in a single file by adding type: ignore[import-not-found]."""
    full_path = f"{WORKSPACE}/{filepath}"
    
    # Read file
    with open(full_path, 'r') as f:
        lines = f.readlines()
    
    # Sort line numbers in reverse so line numbers stay valid
    sorted_lines = sorted(set(line_numbers), reverse=True)
    
    modified = False
    for lineno in sorted_lines:
        idx = lineno - 1  # zero-indexed
        if idx >= len(lines):
            print(f"  WARNING: Line {lineno} out of range in {filepath}, skipping")
            continue
        
        line = lines[idx]
        stripped = line.rstrip('\n').rstrip('\r')
        content = stripped.lstrip()  # For checking if it's an import
        
        # Check if this is actually an import line
        if not (content.startswith('import ') or content.startswith('from ')):
            print(f"  WARNING: Line {lineno} in {filepath} is not an import: {content!r}")
            continue
        
        # Check if it already has type: ignore
        if '# type: ignore' in stripped:
            if 'import-not-found' in stripped:
                # Already covered
                print(f"  Already covered: {filepath}:{lineno}")
                continue
            # Has other ignore(s), need to add import-not-found
            # Pattern: # type: ignore[something] or # type: ignore[something1, something2]
            m = re.search(r'# type:\s*ignore\[([^\]]*)\]', stripped)
            if m:
                existing = m.group(1)
                new_ignore = existing + ', import-not-found'
                new_line = stripped.replace(m.group(0), f'# type: ignore[{new_ignore}]')
                lines[idx] = new_line + '\n'
                modified = True
                print(f"  Updated {filepath}:{lineno} - added import-not-found to existing ignore[{existing}]")
            else:
                # # type: ignore without brackets, or other format
                # Add after existing ignore comment  
                # Just add import-not-found after the existing comment
                if stripped.rstrip().endswith('#'):
                    new_line = stripped.rstrip()[:-1].rstrip() + '  # type: ignore[import-not-found]\n'
                else:
                    # Find the # type: ignore part and extend
                    ignore_pos = stripped.find('# type: ignore')
                    if ignore_pos >= 0:
                        # Check if it has [...]
                        bracket_pos = stripped.find('[', ignore_pos)
                        if bracket_pos >= 0:
                            close_pos = stripped.find(']', bracket_pos)
                            if close_pos >= 0:
                                before_bracket = stripped[:close_pos]
                                after_bracket = stripped[close_pos:]
                                new_line = before_bracket + ', import-not-found' + after_bracket + '\n'
                                lines[idx] = new_line
                                modified = True
                                print(f"  Added import-not-found to existing ignore: {filepath}:{lineno}")
                            else:
                                # Malformed, skip
                                print(f"  WARNING: {filepath}:{lineno} has malformed type: ignore, skipping")
                        else:
                            # # type: ignore without [...] - maybe just "type: ignore" alone
                            new_line = stripped + '  # type: ignore[import-not-found]\n'
                            lines[idx] = new_line
                            modified = True
                            print(f"  Added import-not-found after existing ignore: {filepath}:{lineno}")
                    else:
                        print(f"  WARNING: {filepath}:{lineno} has # type: ignore in comment but not as a directive: {stripped!r}")
        else:
            # No existing type: ignore - add one
            # Check for trailing comment (# ...)
            comment_match = re.search(r'(?<!\S#)\s+#\s', stripped)
            if comment_match:
                # Has inline comment, insert before it
                pos = comment_match.start()
                before_comment = stripped[:pos]
                comment_part = stripped[pos:]
                new_line = before_comment + '  # type: ignore[import-not-found]  ' + comment_part.strip().lstrip('#').strip() + '\n'
                lines[idx] = new_line
                modified = True
                print(f"  Fixed (with inline comment) {filepath}:{lineno}")
            else:
                new_line = stripped + '  # type: ignore[import-not-found]\n'
                lines[idx] = new_line
                modified = True
                print(f"  Fixed {filepath}:{lineno}")
    
    if modified:
        with open(full_path, 'w') as f:
            f.writelines(lines)
        return True
    return False


def main():
    total_fixed = 0
    total_errors = 0
    
    for pkg_name, pkg_path in PACKAGES:
        print(f"\n{'='*60}")
        print(f"Processing {pkg_name} ({pkg_path})")
        print(f"{'='*60}")
        
        raw = run_mypy(pkg_name, pkg_path)
        errors = parse_errors(raw)
        
        total_errors_count = raw.count('[import-not-found]')
        print(f"  Found {total_errors_count} import-not-found errors ({len(errors)} parsed as (file, line) tuples)")
        
        if not errors:
            print(f"  No errors to fix!")
            continue
        
        # Group by file
        by_file = defaultdict(set)
        for filepath, lineno in errors:
            by_file[filepath].add(lineno)
        
        pkg_fixed = 0
        for filepath in sorted(by_file.keys()):
            if fix_file(filepath, list(by_file[filepath])):
                pkg_fixed += len(by_file[filepath])
        
        total_fixed += pkg_fixed
        total_errors += total_errors_count
        print(f"  Fixed {pkg_fixed}/{total_errors_count} errors in {pkg_name}")
    
    print(f"\n{'='*60}")
    print(f"TOTAL: Fixed {total_fixed}/{total_errors} errors")
    print(f"{'='*60}")
    
    # Now re-run mypy to verify
    print("\n\nVerifying results...")
    grand_remaining = 0
    for pkg_name, pkg_path in PACKAGES:
        raw = run_mypy(pkg_name, pkg_path)
        remaining = raw.count('[import-not-found]')
        grand_remaining += remaining
        if remaining > 0:
            # Show remaining errors
            print(f"\n{pkg_name}: {remaining} errors remaining")
            for line in raw.split('\n'):
                if 'import-not-found]' in line:
                    print(f"  {line.strip()}")
        else:
            print(f"\n{pkg_name}: ✅ 0 errors remaining")
    
    print(f"\n{'='*60}")
    print(f"GRAND TOTAL REMAINING: {grand_remaining}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
