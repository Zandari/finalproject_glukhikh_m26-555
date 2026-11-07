import pytest

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import CurrencyNotFoundError


def test_currency_factory():
    assert "[FIAT] USD" in get_currency("USD").get_display_info()
    assert "[CRYPTO] BTC" in get_currency("BTC").get_display_info()


def test_unknown_currency():
    with pytest.raises(CurrencyNotFoundError):
        get_currency("ABC")
