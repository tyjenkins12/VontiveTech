"""Logging configuration for the tax certificate agent."""
import sys
from pathlib import Path
from loguru import logger
from typing import Optional


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    colorize: bool = True
):
    """
    Configure loguru logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file
        colorize: Whether to use colored output (disable for non-TTY)
    """
    # Remove default logger
    logger.remove()

    # Console logging format
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Add console handler
    logger.add(
        sys.stderr,
        format=console_format,
        level=level,
        colorize=colorize,
        backtrace=True,
        diagnose=True
    )

    # Add file handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # File logging format (no colors)
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        )

        logger.add(
            log_file,
            format=file_format,
            level=level,
            rotation="10 MB",  # Rotate when file reaches 10MB
            retention="7 days",  # Keep logs for 7 days
            compression="zip",  # Compress rotated logs
            backtrace=True,
            diagnose=True
        )

        logger.info(f"Logging to file: {log_file}")

    logger.info(f"Logging configured at {level} level")


def get_logger(name: str):
    """
    Get a logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logger.bind(name=name)
