# ontoderive

Ontology derivation package for the Kairon monorepo.

It contains the OntoDerive engines, CLI, MCP server, and pipeline steps used by higher-level knowledge workflows.

## Entry points

```bash
uv run ontoderive --help
uv run python -m ontoderive.mcp_server
```

The external mesh route remains `bos://analysis/ontoderive/derive` through Agora. Internal pipeline consumers import the package directly.

## Validation and evolution pipeline

`validation_steps.py` exposes four pipeline steps:

- `ValidateStep`: verifies one alignment report with `MetaValidateEngine`.
- `BatchValidateStep`: verifies batch items sequentially or with a bounded thread pool.
- `EvolveStep`: generates update suggestions with `MetaEvolveEngine`.
- `BatchEvolveStep`: generates suggestions for batch items sequentially or in parallel.

Batch items carry their own `status`, `result`, and `error`. Items without an alignment report remain `SKIPPED`; they must not be counted as completed. `BatchResult` preserves both the compatibility fields used by existing callers and the aggregate fields emitted by validation steps.

## Verification

Run the focused regression suite with a hard timeout from the Kairon root:

```bash
python3 -c 'import subprocess; subprocess.run(["uv", "run", "pytest", "packages/ontoderive/tests/test_validation_steps.py", "-q", "--tb=short"], check=True, timeout=30)'
```

For adjacent pipeline coverage:

```bash
python3 -c 'import subprocess; subprocess.run(["uv", "run", "pytest", "packages/ontoderive/tests/test_governance_steps.py", "packages/ontoderive/tests/test_validation_steps.py", "-q", "--tb=short"], check=True, timeout=35)'
```
