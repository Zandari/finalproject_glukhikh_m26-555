"""Декораторы для прозрачного логирования доменных операций."""

from functools import wraps
from typing import Any, Callable

from valutatrade_hub.logging_config import get_logger


def log_action(action: str, verbose: bool = False) -> Callable:
    """Логировать успешное завершение и ошибки, не подавляя исключения."""
    logger = get_logger("actions")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            username = "unknown"
            currency = kwargs.get("currency_code", args[1] if len(args) > 1 else "-")
            amount = kwargs.get("amount", args[2] if len(args) > 2 else "-")
            owner = args[0] if args else None
            if owner is not None and hasattr(owner, "current_user_id"):
                username = f"user_id={owner.current_user_id}"
            try:
                result = func(*args, **kwargs)
                details = ""
                if verbose and isinstance(result, dict):
                    details = f" details={result}"
                logger.info(
                    "%s user='%s' currency='%s' amount='%s' result=OK%s",
                    action,
                    username,
                    currency,
                    amount,
                    details,
                )
                return result
            except Exception as exc:
                logger.exception(
                    "%s user='%s' currency='%s' amount='%s' result=ERROR error_type=%s error_message=%s",
                    action,
                    username,
                    currency,
                    amount,
                    type(exc).__name__,
                    str(exc),
                )
                raise

        return wrapper

    return decorator
