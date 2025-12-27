"""
Structured logging utilities for RedGit.

Provides a consistent logging interface that:
- Supports both file and console output
- Integrates with Rich console for styled output
- Respects verbose/quiet modes
- Logs to .redgit/logs/ directory
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler


# Log levels
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL


class RedGitLogger:
    """
    Custom logger for RedGit with Rich console integration.

    Features:
    - File logging to .redgit/logs/
    - Console logging with Rich formatting
    - Verbose mode support
    - Structured log format
    """

    _instance: Optional['RedGitLogger'] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        """Singleton pattern for consistent logging."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        name: str = "redgit",
        level: int = INFO,
        log_to_file: bool = True,
        log_dir: Optional[Path] = None,
        verbose: bool = False
    ):
        """
        Initialize the logger.

        Args:
            name: Logger name
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: Whether to log to file
            log_dir: Directory for log files (default: .redgit/logs/)
            verbose: Enable verbose console output
        """
        if self._initialized:
            return

        self.name = name
        self.verbose = verbose
        self.logger = logging.getLogger(name)
        self.logger.setLevel(DEBUG)  # Capture all, filter at handler level
        self.logger.handlers = []  # Clear existing handlers

        # Console handler with Rich
        console_level = DEBUG if verbose else level
        self._setup_console_handler(console_level)

        # File handler
        if log_to_file:
            self._setup_file_handler(log_dir)

        self._initialized = True

    def _setup_console_handler(self, level: int):
        """Set up Rich console handler."""
        console_handler = RichHandler(
            show_time=False,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=self.verbose
        )
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(console_handler)

    def _setup_file_handler(self, log_dir: Optional[Path] = None):
        """Set up file handler for persistent logging."""
        if log_dir is None:
            log_dir = Path.cwd() / ".redgit" / "logs"

        log_dir.mkdir(parents=True, exist_ok=True)

        # Daily log file
        log_file = log_dir / f"redgit_{datetime.now().strftime('%Y-%m-%d')}.log"

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(DEBUG)  # Log everything to file

        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def set_verbose(self, verbose: bool):
        """Enable or disable verbose mode."""
        self.verbose = verbose
        for handler in self.logger.handlers:
            if isinstance(handler, RichHandler):
                handler.setLevel(DEBUG if verbose else INFO)

    def debug(self, message: str, *args, **kwargs):
        """Log debug message."""
        self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        """Log info message."""
        self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        """Log warning message."""
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        """Log error message."""
        self.logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        """Log critical message."""
        self.logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        """Log exception with traceback."""
        self.logger.exception(message, *args, **kwargs)

    # Convenience methods for common patterns
    def success(self, message: str):
        """Log success message (info level with success styling)."""
        self.info(f"[green]✓[/green] {message}")

    def fail(self, message: str):
        """Log failure message (error level with failure styling)."""
        self.error(f"[red]✗[/red] {message}")

    def step(self, message: str):
        """Log a step in a process."""
        self.info(f"[cyan]→[/cyan] {message}")

    def command(self, cmd: str):
        """Log a command being executed."""
        self.debug(f"[dim]$ {cmd}[/dim]")


# Global logger instance
_logger: Optional[RedGitLogger] = None


def get_logger(
    name: str = "redgit",
    verbose: bool = False,
    log_to_file: bool = True
) -> RedGitLogger:
    """
    Get or create the global logger instance.

    Args:
        name: Logger name
        verbose: Enable verbose output
        log_to_file: Whether to log to file

    Returns:
        RedGitLogger instance
    """
    global _logger
    if _logger is None:
        _logger = RedGitLogger(
            name=name,
            verbose=verbose,
            log_to_file=log_to_file
        )
    return _logger


def setup_logging(
    verbose: bool = False,
    quiet: bool = False,
    log_to_file: bool = True,
    log_dir: Optional[Path] = None
) -> RedGitLogger:
    """
    Set up logging for a RedGit session.

    Args:
        verbose: Enable verbose (debug) output
        quiet: Suppress info messages (only warnings/errors)
        log_to_file: Whether to log to file
        log_dir: Directory for log files

    Returns:
        Configured RedGitLogger instance
    """
    level = DEBUG if verbose else (WARNING if quiet else INFO)

    logger = RedGitLogger(
        level=level,
        log_to_file=log_to_file,
        log_dir=log_dir,
        verbose=verbose
    )

    return logger


def log_operation(operation: str):
    """
    Decorator to log function entry/exit.

    Usage:
        @log_operation("Processing files")
        def process_files():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger()
            logger.debug(f"Starting: {operation}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Completed: {operation}")
                return result
            except Exception as e:
                logger.error(f"Failed: {operation} - {e}")
                raise
        return wrapper
    return decorator


# Structured log context
class LogContext:
    """
    Context manager for structured logging with context.

    Usage:
        with LogContext(logger, "Processing commit", issue="PROJ-123"):
            # Do work
            pass
    """

    def __init__(self, logger: RedGitLogger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context

    def __enter__(self):
        context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
        self.logger.debug(f"[{self.operation}] Starting ({context_str})")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(f"[{self.operation}] Failed: {exc_val}")
        else:
            self.logger.debug(f"[{self.operation}] Completed")
        return False
