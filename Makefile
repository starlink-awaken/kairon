.PHONY: test lint install clean

# Install all packages in monorepo
install:
	uv sync

# Run tests on all packages/* — per-package, non-blocking
test:
	@echo "=== 运行所有包测试 ==="; \
	fail=0; \
	for pkg in packages/*/; do \
		name=$$(basename $$pkg); \
		echo "--- [$$name] ---"; \
		if ! (cd $$pkg && uv run python -m pytest tests/ -q); then \
			fail=1; \
		fi; \
	done; \
	echo "=== 全部完成 ==="; \
	test $$fail -eq 0

# Fast: unit tests only (skip integration/benchmarks)
test-fast:
	@echo "=== 快速测试（仅 unit）==="; \
	fail=0; \
	for pkg in packages/*/; do \
		name=$$(basename $$pkg); \
		echo "--- [$$name] ---"; \
		if [ -d "$$pkg/tests" ]; then \
			if ! (cd $$pkg && uv run python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/benchmarks); then \
				fail=1; \
			fi; \
		else \
			echo "  ⏭️ 跳过"; \
		fi; \
	done; \
	echo "=== 全部完成 ==="; \
	test $$fail -eq 0

# Fast: unit tests only for changed packages (git diff)
test-diff:
	@echo "=== 差异测试（仅修改的包）==="; \
	fail=0; \
	for pkg in $$(git diff --name-only HEAD 2>/dev/null | grep "^packages/" | cut -d/ -f1-2 | sort -u); do \
		name=$$(basename $$pkg); \
		echo "--- [$$name] ---"; \
		if [ -d "$$pkg/tests" ]; then \
			if ! (cd $$pkg && uv run python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/benchmarks 2>/dev/null); then \
				fail=1; \
			fi; \
		else \
			echo "  ⏭️ 跳过"; \
		fi; \
	done; \
	if [ $$fail -eq 0 ] && [ -z "$${pkg:-}" ]; then \
		echo "  ⏭️  无修改的包"; \
	fi; \
	echo "=== 全部完成 ==="; \
	test $$fail -eq 0

# Parallel: unit tests on all packages simultaneously (max 4 jobs)
test-parallel:
	@echo "=== 并行测试（最多 4 并发）==="; \
	pkgs=""; \
	for pkg in packages/*/; do \
		if [ -d "$$pkg/tests" ]; then \
			pkgs="$$pkgs $$(basename $$pkg)"; \
		fi; \
	done; \
	echo "Packages: $$pkgs"; \
	echo "$$pkgs" | tr ' ' '\n' | xargs -P4 -I{} sh -c ' \
		echo "--- [{}] ---"; \
		cd packages/{} && uv run python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/benchmarks 2>&1 || echo "FAILED: {}"; \
	'

# Lint all packages with ruff
lint:
	ruff check packages/

# Format all packages with ruff
format:
	ruff format packages/

# Clean build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv/
