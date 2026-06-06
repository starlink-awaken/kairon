"""Backward-compat re-export — delegates to kairon-utils."""
from kairon_utils.error_handler import (  # noqa: F401
    ErrorContext,
    ErrorHandler,
    create_error_handler,
    handle_exception,
)
