"""Tests for error_system — DSLError hierarchy, error collectors, recovery manager."""

from agent_runtime.error_system import (
    DSLError,
    ErrorCode,
    ErrorCollector,
    ErrorRecoveryManager,
    ErrorSeverity,
    FixSuggestion,
    LexicalError,
    RuntimeError_,
    SemanticError,
    SourceLocation,
    SyntaxError_,
    TypeError_,
    create_source_location,
    format_source_location,
)


class TestErrorCodes:
    """ErrorCode enum values are correct."""

    def test_syntax_error_codes(self):
        assert ErrorCode.SYX001_UNEXPECTED_TOKEN == "SYX001"
        assert ErrorCode.SYX002_MISSING_TOKEN == "SYX002"
        assert ErrorCode.SYX003_INVALID_SYNTAX == "SYX003"

    def test_lexical_error_codes(self):
        assert ErrorCode.LEX101_UNCLOSED_STRING == "LEX101"
        assert ErrorCode.LEX102_INVALID_ESCAPE == "LEX102"

    def test_runtime_error_codes(self):
        assert ErrorCode.RUN501_EXECUTION_FAILED == "RUN501"
        assert ErrorCode.RUN502_TIMEOUT == "RUN502"

    def test_io_error_code(self):
        assert ErrorCode.IO701_FILE_NOT_FOUND == "IO701"


class TestSourceLocation:
    """SourceLocation creation and formatting."""

    def test_default_location(self):
        loc = SourceLocation()
        assert loc.file == "<unknown>"
        assert loc.line == 1
        assert loc.column == 1

    def test_create_source_location(self):
        loc = create_source_location("test.dsl", 10, 5, length=3)
        assert loc.file == "test.dsl"
        assert loc.line == 10
        assert loc.column == 5
        assert loc.length == 3

    def test_format_source_location(self):
        loc = SourceLocation(file="script.dsl", line=42, column=7)
        assert format_source_location(loc) == "script.dsl:42:7"


class TestDSLError:
    """Base DSLError construction and helpers."""

    def test_default_construction(self):
        err = DSLError()
        assert err.code == ErrorCode.RUN501_EXECUTION_FAILED
        assert err.severity == ErrorSeverity.ERROR
        assert err.loc is not None
        assert err.context == {}
        assert err.caused_by is None
        assert err.suggestions == []

    def test_is_error_and_is_warning(self):
        err = DSLError(severity=ErrorSeverity.ERROR)
        assert err.is_error()
        assert not err.is_warning()

        warn = DSLError(severity=ErrorSeverity.WARNING)
        assert warn.is_warning()
        assert not warn.is_error()

    def test_add_suggestion(self):
        err = DSLError()
        suggestion = FixSuggestion(message="Try something else", priority=8)
        result = err.add_suggestion(suggestion)
        assert result is err  # returns self for chaining
        assert len(err.suggestions) == 1
        assert err.suggestions[0].message == "Try something else"

    def test_to_short_string(self):
        loc = SourceLocation(file="test.dsl", line=5, column=3)
        err = DSLError(ErrorCode.SYX003_INVALID_SYNTAX, "Bad syntax", loc=loc)
        short = err.to_short_string()
        assert "SYX003" in short
        assert "Bad syntax" in short
        assert "test.dsl:5:3" in short


class TestSyntaxError:
    """SyntaxError_ factory methods."""

    def test_unexpected_token(self):
        loc = SourceLocation(file="e.dsl", line=1, column=1)
        err = SyntaxError_.unexpected_token("}", [";", ":"], loc)
        assert err.code == ErrorCode.SYX001_UNEXPECTED_TOKEN
        assert "unexpected token" in str(err).lower()
        assert len(err.suggestions) >= 1
        assert err.suggestions[0].priority == 10

    def test_missing_token(self):
        loc = SourceLocation(file="e.dsl", line=2, column=5)
        err = SyntaxError_.missing_token("end", loc)
        assert err.code == ErrorCode.SYX002_MISSING_TOKEN
        assert "Missing" in str(err)
        assert err.suggestions[0].action == "insert"


class TestLexicalError:
    """LexicalError factory methods."""

    def test_unclosed_string(self):
        err = LexicalError.unclosed_string(SourceLocation())
        assert err.code == ErrorCode.LEX101_UNCLOSED_STRING
        assert "Unclosed" in str(err)
        assert err.suggestions[0].action == "insert"

    def test_invalid_escape(self):
        loc = SourceLocation(file="x.dsl", line=3, column=10)
        err = LexicalError.invalid_escape("\\z", loc)
        assert err.code == ErrorCode.LEX102_INVALID_ESCAPE
        assert "\\z" in str(err)


class TestTypeError:
    """TypeError_ factory methods."""

    def test_type_mismatch(self):
        loc = SourceLocation()
        err = TypeError_.type_mismatch("number", "string", loc)
        assert err.code == ErrorCode.TYP201_TYPE_MISMATCH
        assert err.expected_type == "number"
        assert err.actual_type == "string"
        assert "number" in str(err)
        assert "string" in str(err)


class TestSemanticError:
    """SemanticError factory methods."""

    def test_undefined_symbol(self):
        err = SemanticError.undefined_symbol("foo", SourceLocation())
        assert err.code == ErrorCode.SEM301_UNDEFINED_SYMBOL
        assert "foo" in str(err)

    def test_duplicate_declaration(self):
        first = SourceLocation(file="a.dsl", line=5, column=1)
        second = SourceLocation(file="a.dsl", line=10, column=1)
        err = SemanticError.duplicate_declaration("bar", first, second)
        assert err.code == ErrorCode.SEM302_DUPLICATE_DECLARATION
        assert "bar" in str(err)
        assert "5" in str(err)

    def test_circular_dependency(self):
        err = SemanticError.circular_dependency(["A", "B", "C"], SourceLocation())
        assert err.code == ErrorCode.SEM303_CIRCULAR_DEPENDENCY
        assert "A -> B -> C" in str(err)


class TestRuntimeError:
    """RuntimeError_ factory methods."""

    def test_execution_failed(self):
        loc = SourceLocation()
        err = RuntimeError_.execution_failed("Connection refused", loc)
        assert err.code == ErrorCode.RUN501_EXECUTION_FAILED
        assert "Connection refused" in str(err)

    def test_stack_depth_exceeded(self):
        loc = SourceLocation()
        err = RuntimeError_.stack_depth_exceeded(101, 100, loc)
        assert err.code == ErrorCode.RUN506_STACK_DEPTH_EXCEEDED
        assert "101" in str(err)
        assert "100" in str(err)


class TestErrorCollector:
    """ErrorCollector accumulates errors and warnings correctly."""

    def test_empty_collector(self):
        c = ErrorCollector()
        assert not c.has_errors()
        assert not c.has_warnings()
        assert c.error_count == 0
        assert c.warning_count == 0

    def test_add_error(self):
        c = ErrorCollector()
        c.add_error(DSLError())
        assert c.has_errors()
        assert c.error_count == 1

    def test_add_warning(self):
        c = ErrorCollector()
        c.add_error(DSLError(severity=ErrorSeverity.WARNING))
        assert c.has_warnings()
        assert c.warning_count == 1
        assert not c.has_errors()

    def test_add_errors_multiple(self):
        c = ErrorCollector()
        c.add_errors([
            DSLError(severity=ErrorSeverity.ERROR),
            DSLError(severity=ErrorSeverity.WARNING),
            DSLError(severity=ErrorSeverity.WARNING),
        ])
        assert c.error_count == 1
        assert c.warning_count == 2

    def test_clear(self):
        c = ErrorCollector()
        c.add_error(DSLError())
        c.clear()
        assert c.error_count == 0
        assert c.warning_count == 0

    def test_get_errors_returns_copy(self):
        c = ErrorCollector()
        c.add_error(DSLError())
        errors = c.get_errors()
        assert len(errors) == 1
        errors.clear()
        assert c.error_count == 1  # original unchanged


class TestErrorRecoveryManager:
    """ErrorRecoveryManager retry attempt tracking."""

    def test_default_max_attempts(self):
        mgr = ErrorRecoveryManager()
        assert mgr.can_recover()

    def test_try_recover_returns_false(self):
        mgr = ErrorRecoveryManager(max_attempts=3)
        assert not mgr.try_recover({})

    def test_can_recover_exhausted(self):
        mgr = ErrorRecoveryManager(max_attempts=2)
        assert mgr.try_recover({}) is False
        assert mgr.try_recover({}) is False
        assert not mgr.can_recover()

    def test_reset(self):
        mgr = ErrorRecoveryManager(max_attempts=1)
        mgr.try_recover({})
        assert not mgr.can_recover()
        mgr.reset()
        assert mgr.can_recover()
