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
		if ! (cd $$pkg && uv run python -m pytest tests/ -q 2>/dev/null); then \
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
			if ! (cd $$pkg && python3 -m pytest tests/ -q --ignore=tests/integration --ignore=tests/benchmarks); then \
				fail=1; \
			fi; \
		else \
			echo "  ⏭️ 跳过"; \
		fi; \
	done; \
	echo "=== 全部完成 ==="; \
	test $$fail -eq 0

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
