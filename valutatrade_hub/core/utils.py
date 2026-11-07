"""Валидация и конвертация валютных сумм."""

import math
from typing import Any

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError

# Учебные значения из задания. Они используются только как offline-заглушка.
DEMO_RATES = {
    "BTC_USD": 59337.21,
    "ETH_USD": 3720.00,
    "SOL_USD": 145.12,
    "EUR_USD": 1.0786,
    "GBP_USD": 1.23,
    "RUB_USD": 0.01016,
}


def validate_amount(amount: Any) -> float:
    """Проверить, что amount — конечное положительное число."""
    if isinstance(amount, bool):
        raise ValueError("'amount' должен быть положительным числом")
    try:
        number = float(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("'amount' должен быть положительным числом") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return number


def validate_currency_code(code: str) -> str:
    """Проверить формат и наличие валюты в реестре."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    normalized = code.strip().upper()
    get_currency(normalized)
    return normalized


def _pair_rate(pairs: dict[str, Any], source: str, target: str) -> float | None:
    """Получить прямой/обратный курс из словаря пар."""
    if source == target:
        return 1.0
    direct = pairs.get(f"{source}_{target}")
    if direct is not None:
        return float(direct.get("rate", direct) if isinstance(direct, dict) else direct)
    reverse = pairs.get(f"{target}_{source}")
    if reverse is not None:
        value = float(reverse.get("rate", reverse) if isinstance(reverse, dict) else reverse)
        return 1.0 / value if value else None
    return None


def get_conversion_rate(source: str, target: str, rates: dict | None = None) -> float:
    """Получить курс, при необходимости используя USD как промежуточную валюту."""
    source = validate_currency_code(source)
    target = validate_currency_code(target)
    if source == target:
        return 1.0
    rates = rates or {}
    pairs = rates.get("pairs", rates)
    direct = _pair_rate(pairs, source, target)
    if direct is not None:
        return direct
    to_usd = _pair_rate(pairs, source, "USD")
    from_usd = _pair_rate(pairs, "USD", target)
    if to_usd is not None and from_usd is not None:
        return to_usd * from_usd
    # Offline-заглушки хранят все значения относительно USD.
    fallback = dict(DEMO_RATES)
    fallback.update({key: value for key, value in pairs.items() if key in DEMO_RATES})
    to_usd = _pair_rate(fallback, source, "USD")
    from_usd = _pair_rate(fallback, "USD", target)
    if to_usd is not None and from_usd is not None:
        return to_usd * from_usd
    raise ApiRequestError(f"курс {source}→{target} отсутствует в локальном кеше")


def convert_amount(amount: float, source: str, target: str, rates: dict | None = None) -> float:
    """Конвертировать сумму из source в target."""
    return validate_amount(amount) * get_conversion_rate(source, target, rates)
