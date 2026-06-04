"""Tests for sandbox — safe Python code execution with validation and timeout."""

from agent_runtime.sandbox import Sandbox


class TestSandboxValidation:
    """Sandbox.validate_code rejects dangerous patterns."""

    def test_simple_expression_valid(self):
        valid, _ = Sandbox.validate_code("result = 1 + 1")
        assert valid is True

    def test_no_imports_allowed(self):
        valid, msg = Sandbox.validate_code("import os")
        assert valid is False
        assert "No imports allowed" in msg

    def test_no_from_imports_allowed(self):
        valid, msg = Sandbox.validate_code("from sys import exit")
        assert valid is False
        assert "No imports allowed" in msg

    def test_invalid_syntax_rejected(self):
        valid, msg = Sandbox.validate_code("result = ")
        assert valid is False
        assert msg  # Syntax error message

    def test_function_definition_valid(self):
        valid, _ = Sandbox.validate_code("def foo(x): return x + 1")
        assert valid is True


class TestSandboxExecution:
    """Sandbox.execute runs code safely."""

    def test_successful_execution(self):
        result = Sandbox.execute("print('hello world')")
        assert result.success is True
        assert "hello world" in result.stdout

    def test_import_blocked(self):
        result = Sandbox.execute("import os")
        assert result.success is False
        assert "No imports allowed" in result.error

    def test_syntax_error_reported(self):
        result = Sandbox.execute("if True")
        assert result.success is False

    def test_function_definition_and_execution(self):
        code = """
def add(a, b):
    return a + b
print(add(3, 4))
"""
        result = Sandbox.execute(code)
        assert result.success is True
        assert "7" in result.stdout

    def test_duration_is_positive(self):
        result = Sandbox.execute("result = 1 + 1")
        assert result.success is True
        assert result.duration_ms > 0

    def test_print_captured_in_stdout(self):
        result = Sandbox.execute("print('hello world')")
        assert result.success is True
        assert "hello world" in result.stdout


class TestSandboxTimeout:
    """Sandbox timeout enforcement."""

    def test_short_timeout_triggers(self):
        # Use a loop that runs long enough to trigger timeout
        # Note: signal.alarm(int()) rounds down, so timeout_sec must be >= 1
        result = Sandbox.execute("while True: pass", timeout_sec=1)
        assert result.success is False
        assert "Timeout" in result.error

    def test_fast_code_passes_with_short_timeout(self):
        result = Sandbox.execute("print('fast')", timeout_sec=1)
        assert result.success is True
        assert "fast" in result.stdout


class TestSandboxOutputLimits:
    """Sandbox max_output_len truncation."""

    def test_long_output_truncated(self):
        code = "print('x' * 500)"
        result = Sandbox.execute(code, max_output_len=50)
        assert result.success is True
        assert len(result.stdout) <= 53  # 50 chars + "..."

    def test_short_output_not_truncated(self):
        code = "print('short')"
        result = Sandbox.execute(code, max_output_len=100)
        assert result.success is True
        assert result.stdout == "short"
