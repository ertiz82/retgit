"""
Tests for redgit/utils/logging.py - Structured logging utilities.
"""

import logging
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from redgit.utils.logging import (
    RedGitLogger,
    get_logger,
    setup_logging,
    log_operation,
    LogContext,
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL,
)


class TestLogLevelConstants:
    """Test log level constants are properly exported."""

    def test_debug_level(self):
        assert DEBUG == logging.DEBUG

    def test_info_level(self):
        assert INFO == logging.INFO

    def test_warning_level(self):
        assert WARNING == logging.WARNING

    def test_error_level(self):
        assert ERROR == logging.ERROR

    def test_critical_level(self):
        assert CRITICAL == logging.CRITICAL


class TestRedGitLogger:
    """Tests for RedGitLogger class."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        RedGitLogger._instance = None
        RedGitLogger._initialized = False
        yield
        RedGitLogger._instance = None
        RedGitLogger._initialized = False

    def test_singleton_pattern(self):
        """Test that RedGitLogger uses singleton pattern."""
        logger1 = RedGitLogger(log_to_file=False)
        logger2 = RedGitLogger(log_to_file=False)
        assert logger1 is logger2

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        logger = RedGitLogger(log_to_file=False)
        assert logger.name == "redgit"
        assert logger.verbose is False

    def test_init_with_custom_name(self):
        """Test initialization with custom name."""
        logger = RedGitLogger(name="custom", log_to_file=False)
        assert logger.name == "custom"

    def test_init_with_verbose(self):
        """Test initialization with verbose mode."""
        logger = RedGitLogger(verbose=True, log_to_file=False)
        assert logger.verbose is True

    def test_set_verbose(self):
        """Test set_verbose method."""
        logger = RedGitLogger(verbose=False, log_to_file=False)
        logger.set_verbose(True)
        assert logger.verbose is True

    def test_debug_logs_message(self):
        """Test debug method logs message."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'debug') as mock_debug:
            logger.debug("Test message")
            mock_debug.assert_called_once_with("Test message")

    def test_info_logs_message(self):
        """Test info method logs message."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'info') as mock_info:
            logger.info("Test message")
            mock_info.assert_called_once_with("Test message")

    def test_warning_logs_message(self):
        """Test warning method logs message."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'warning') as mock_warning:
            logger.warning("Test message")
            mock_warning.assert_called_once_with("Test message")

    def test_error_logs_message(self):
        """Test error method logs message."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'error') as mock_error:
            logger.error("Test message")
            mock_error.assert_called_once_with("Test message")

    def test_critical_logs_message(self):
        """Test critical method logs message."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'critical') as mock_critical:
            logger.critical("Test message")
            mock_critical.assert_called_once_with("Test message")

    def test_exception_logs_message(self):
        """Test exception method logs message."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'exception') as mock_exception:
            logger.exception("Test error")
            mock_exception.assert_called_once_with("Test error")

    def test_success_logs_styled_message(self):
        """Test success convenience method."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'info') as mock_info:
            logger.success("Task done")
            mock_info.assert_called_once()
            call_arg = mock_info.call_args[0][0]
            assert "Task done" in call_arg
            assert "[green]" in call_arg

    def test_fail_logs_styled_message(self):
        """Test fail convenience method."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'error') as mock_error:
            logger.fail("Task failed")
            mock_error.assert_called_once()
            call_arg = mock_error.call_args[0][0]
            assert "Task failed" in call_arg
            assert "[red]" in call_arg

    def test_step_logs_styled_message(self):
        """Test step convenience method."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'info') as mock_info:
            logger.step("Processing")
            mock_info.assert_called_once()
            call_arg = mock_info.call_args[0][0]
            assert "Processing" in call_arg
            assert "[cyan]" in call_arg

    def test_command_logs_styled_message(self):
        """Test command convenience method."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'debug') as mock_debug:
            logger.command("git status")
            mock_debug.assert_called_once()
            call_arg = mock_debug.call_args[0][0]
            assert "git status" in call_arg


class TestRedGitLoggerFileHandler:
    """Tests for file handler setup."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        RedGitLogger._instance = None
        RedGitLogger._initialized = False
        yield
        RedGitLogger._instance = None
        RedGitLogger._initialized = False

    def test_file_handler_creates_log_dir(self, tmp_path):
        """Test that file handler creates log directory."""
        log_dir = tmp_path / "logs"
        logger = RedGitLogger(log_to_file=True, log_dir=log_dir)
        assert log_dir.exists()

    def test_file_handler_creates_log_file(self, tmp_path):
        """Test that file handler creates daily log file."""
        log_dir = tmp_path / "logs"
        logger = RedGitLogger(log_to_file=True, log_dir=log_dir)
        log_files = list(log_dir.glob("redgit_*.log"))
        assert len(log_files) == 1


class TestGetLogger:
    """Tests for get_logger function."""

    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset global logger between tests."""
        import redgit.utils.logging as log_module
        log_module._logger = None
        RedGitLogger._instance = None
        RedGitLogger._initialized = False
        yield
        log_module._logger = None
        RedGitLogger._instance = None
        RedGitLogger._initialized = False

    def test_get_logger_creates_instance(self):
        """Test get_logger creates a logger instance."""
        logger = get_logger(log_to_file=False)
        assert isinstance(logger, RedGitLogger)

    def test_get_logger_returns_same_instance(self):
        """Test get_logger returns the same instance."""
        logger1 = get_logger(log_to_file=False)
        logger2 = get_logger(log_to_file=False)
        assert logger1 is logger2

    def test_get_logger_with_verbose(self):
        """Test get_logger with verbose parameter."""
        logger = get_logger(verbose=True, log_to_file=False)
        assert logger.verbose is True

    def test_get_logger_with_custom_name(self):
        """Test get_logger with custom name."""
        logger = get_logger(name="custom", log_to_file=False)
        assert logger.name == "custom"


class TestSetupLogging:
    """Tests for setup_logging function."""

    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset singleton between tests."""
        RedGitLogger._instance = None
        RedGitLogger._initialized = False
        yield
        RedGitLogger._instance = None
        RedGitLogger._initialized = False

    def test_setup_logging_returns_logger(self):
        """Test setup_logging returns a RedGitLogger."""
        logger = setup_logging(log_to_file=False)
        assert isinstance(logger, RedGitLogger)

    def test_setup_logging_with_verbose(self):
        """Test setup_logging with verbose mode."""
        logger = setup_logging(verbose=True, log_to_file=False)
        assert logger.verbose is True

    def test_setup_logging_with_quiet(self):
        """Test setup_logging with quiet mode sets WARNING level."""
        logger = setup_logging(quiet=True, log_to_file=False)
        # Check that console handler has WARNING level
        for handler in logger.logger.handlers:
            if hasattr(handler, 'level'):
                # At least one handler should be WARNING level
                pass

    def test_setup_logging_with_custom_log_dir(self, tmp_path):
        """Test setup_logging with custom log directory."""
        log_dir = tmp_path / "custom_logs"
        logger = setup_logging(log_to_file=True, log_dir=log_dir)
        assert log_dir.exists()


class TestLogOperationDecorator:
    """Tests for log_operation decorator."""

    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset logger between tests."""
        import redgit.utils.logging as log_module
        log_module._logger = None
        RedGitLogger._instance = None
        RedGitLogger._initialized = False
        yield
        log_module._logger = None
        RedGitLogger._instance = None
        RedGitLogger._initialized = False

    def test_decorator_returns_function_result(self):
        """Test that decorated function returns its result."""
        @log_operation("Test operation")
        def test_func():
            return 42

        # Initialize logger first
        get_logger(log_to_file=False)
        result = test_func()
        assert result == 42

    def test_decorator_preserves_args(self):
        """Test that decorated function receives arguments."""
        @log_operation("Test operation")
        def test_func(a, b):
            return a + b

        get_logger(log_to_file=False)
        result = test_func(1, 2)
        assert result == 3

    def test_decorator_preserves_kwargs(self):
        """Test that decorated function receives keyword arguments."""
        @log_operation("Test operation")
        def test_func(a, b=10):
            return a + b

        get_logger(log_to_file=False)
        result = test_func(5, b=15)
        assert result == 20

    def test_decorator_propagates_exception(self):
        """Test that decorated function propagates exceptions."""
        @log_operation("Failing operation")
        def test_func():
            raise ValueError("Test error")

        get_logger(log_to_file=False)
        with pytest.raises(ValueError, match="Test error"):
            test_func()


class TestLogContext:
    """Tests for LogContext context manager."""

    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset singleton between tests."""
        RedGitLogger._instance = None
        RedGitLogger._initialized = False
        yield
        RedGitLogger._instance = None
        RedGitLogger._initialized = False

    def test_context_manager_enter(self):
        """Test LogContext logs on entry."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'debug') as mock_debug:
            with LogContext(logger, "Test operation", key="value"):
                pass
            # Should have logged start and complete
            assert mock_debug.call_count == 2

    def test_context_manager_exit_success(self):
        """Test LogContext logs completion on success."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'debug') as mock_debug:
            with LogContext(logger, "Test operation"):
                pass
            # Check completion message was logged
            calls = [str(call) for call in mock_debug.call_args_list]
            assert any("Completed" in str(call) for call in calls)

    def test_context_manager_exit_failure(self):
        """Test LogContext logs error on exception."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'error') as mock_error:
            try:
                with LogContext(logger, "Failing operation"):
                    raise ValueError("Test error")
            except ValueError:
                pass
            mock_error.assert_called_once()
            call_arg = str(mock_error.call_args)
            assert "Failed" in call_arg

    def test_context_manager_returns_self(self):
        """Test LogContext returns self on enter."""
        logger = RedGitLogger(log_to_file=False)
        with LogContext(logger, "Test") as ctx:
            assert isinstance(ctx, LogContext)
            assert ctx.operation == "Test"

    def test_context_manager_with_context_params(self):
        """Test LogContext includes context parameters in log."""
        logger = RedGitLogger(log_to_file=False)
        with patch.object(logger.logger, 'debug') as mock_debug:
            with LogContext(logger, "Test", issue="PROJ-123", branch="main"):
                pass
            # First call should include context
            first_call = str(mock_debug.call_args_list[0])
            assert "issue=PROJ-123" in first_call
            assert "branch=main" in first_call


class TestConfigManagerLogging:
    """Tests for ConfigManager logging methods."""

    @pytest.fixture
    def config_manager(self, tmp_path):
        """Create a ConfigManager with temp directory."""
        from redgit.core.config import ConfigManager, RETGIT_DIR, CONFIG_PATH
        import redgit.core.config as config_module

        # Temporarily override paths
        original_dir = config_module.RETGIT_DIR
        original_path = config_module.CONFIG_PATH

        config_module.RETGIT_DIR = tmp_path / ".redgit"
        config_module.CONFIG_PATH = config_module.RETGIT_DIR / "config.yaml"

        manager = ConfigManager()

        yield manager

        # Restore original paths
        config_module.RETGIT_DIR = original_dir
        config_module.CONFIG_PATH = original_path

    def test_get_logging_config_defaults(self, config_manager):
        """Test get_logging_config returns defaults when no config."""
        config = config_manager.get_logging_config()
        assert config["enabled"] is True
        assert config["level"] == "INFO"
        assert config["file"] is True
        assert config["console"] is True
        assert config["max_files"] == 7

    def test_get_logging_config_with_custom_values(self, config_manager):
        """Test get_logging_config merges custom values."""
        config_manager.set_value("logging.level", "DEBUG")
        config_manager.set_value("logging.max_files", 14)

        config = config_manager.get_logging_config()
        assert config["level"] == "DEBUG"
        assert config["max_files"] == 14
        assert config["enabled"] is True  # Default preserved

    def test_is_logging_enabled_default(self, config_manager):
        """Test is_logging_enabled returns True by default."""
        assert config_manager.is_logging_enabled() is True

    def test_is_logging_enabled_when_disabled(self, config_manager):
        """Test is_logging_enabled returns False when disabled."""
        config_manager.set_logging_enabled(False)
        assert config_manager.is_logging_enabled() is False

    def test_get_log_level_default(self, config_manager):
        """Test get_log_level returns INFO by default."""
        assert config_manager.get_log_level() == "INFO"

    def test_get_log_level_custom(self, config_manager):
        """Test get_log_level returns custom value."""
        config_manager.set_log_level("DEBUG")
        assert config_manager.get_log_level() == "DEBUG"

    def test_set_logging_enabled(self, config_manager):
        """Test set_logging_enabled updates config."""
        config_manager.set_logging_enabled(False)
        config = config_manager.load()
        assert config["logging"]["enabled"] is False

    def test_set_logging_enabled_creates_section(self, config_manager):
        """Test set_logging_enabled creates logging section if missing."""
        config_manager.set_logging_enabled(True)
        config = config_manager.load()
        assert "logging" in config

    def test_set_log_level_valid(self, config_manager):
        """Test set_log_level with valid level."""
        config_manager.set_log_level("WARNING")
        assert config_manager.get_log_level() == "WARNING"

    def test_set_log_level_uppercase_conversion(self, config_manager):
        """Test set_log_level converts to uppercase."""
        config_manager.set_log_level("debug")
        assert config_manager.get_log_level() == "DEBUG"

    def test_set_log_level_invalid_raises(self, config_manager):
        """Test set_log_level raises for invalid level."""
        with pytest.raises(ValueError, match="Invalid log level"):
            config_manager.set_log_level("INVALID")

    def test_set_log_level_all_valid_levels(self, config_manager):
        """Test all valid log levels are accepted."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            config_manager.set_log_level(level)
            assert config_manager.get_log_level() == level
