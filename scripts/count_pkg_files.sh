#!/bin/bash
for pkg in kairon-lib-events kairon-utils kairon-plugin-sdk kairon-observability kairon-pipeline eidos kos minerva ontoderive iris forge codeanalyze kronos core-models health-profile sophia; do
    src_count=$(find "/Users/xiamingxing/Workspace/projects/kairon/packages/$pkg/src" -name '*.py' 2>/dev/null | wc -l)
    test_count=$(find "/Users/xiamingxing/Workspace/projects/kairon/packages/$pkg/tests" -name '*.py' 2>/dev/null | wc -l)
    readme=$([ -f "/Users/xiamingxing/Workspace/projects/kairon/packages/$pkg/README.md" ] && echo "yes" || echo "no")
    claude=$([ -f "/Users/xiamingxing/Workspace/projects/kairon/packages/$pkg/CLAUDE.md" ] && echo "yes" || echo "no")
    echo "$pkg|$src_count|$test_count|$readme|$claude"
done
