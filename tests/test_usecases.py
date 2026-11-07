"""Проверки основных пользовательских сценариев Core Service."""

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import UseCases


class MemoryDatabase:
    """Изолированное in-memory хранилище для тестов usecases."""

    def __init__(self):
        self.users = []
        self.portfolios = []
        self.rates = {"pairs": {}, "last_refresh": None}

    def load_users(self):
        return self.users

    def save_users(self, records):
        self.users = records

    def load_portfolios(self):
        return self.portfolios

    def save_portfolios(self, records):
        self.portfolios = records

    def load_rates(self):
        return self.rates

    def save_rates(self, records):
        self.rates = records


def create_logged_in_app():
    """Создать приложение с тестовым пользователем и активной сессией."""
    app = UseCases(database=MemoryDatabase())
    app.register("alice", "1234")
    app.login("alice", "1234")
    return app


def test_register_login_buy_sell_portfolio_cycle():
    app = create_logged_in_app()
    app.deposit("USD", 5000)

    purchase = app.buy("BTC", 0.01)
    sale = app.sell("BTC", 0.002)
    portfolio = app.show_portfolio()

    assert purchase["after"] == 0.01
    assert abs(sale["after"] - 0.008) < 1e-10
    balances = {row["currency"]: row["balance"] for row in portfolio["rows"]}
    assert abs(balances["BTC"] - 0.008) < 1e-10
    assert balances["USD"] > 0
    assert portfolio["username"] == "alice"


def test_buy_rejects_insufficient_usd_balance():
    app = create_logged_in_app()
    app.deposit("USD", 10)

    try:
        app.buy("BTC", 1)
    except InsufficientFundsError as exc:
        assert exc.code == "USD"
    else:
        raise AssertionError("Ожидалась ошибка недостатка средств")


def test_buy_rejects_unknown_currency():
    app = create_logged_in_app()

    try:
        app.buy("ABC", 1)
    except CurrencyNotFoundError:
        pass
    else:
        raise AssertionError("Ожидалась ошибка неизвестной валюты")


def test_get_rate_rejects_stale_cache():
    app = create_logged_in_app()
    app.database.rates = {
        "pairs": {
            "BTC_USD": {
                "rate": 50000.0,
                "updated_at": "2020-01-01T00:00:00Z",
                "source": "CoinGecko",
            }
        },
        "last_refresh": "2020-01-01T00:00:00Z",
    }

    try:
        app.get_rate("BTC", "USD")
    except ApiRequestError as exc:
        assert "устарел" in str(exc)
    else:
        raise AssertionError("Ожидалась ошибка устаревшего кеша")
