"""Прикладные сценарии: регистрация, сессия, портфель и сделки."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import (
    DEMO_RATES,
    get_conversion_rate,
    validate_amount,
    validate_currency_code,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader


class UseCases:
    """Оркестратор бизнес-операций Core Service."""

    def __init__(self, database: DatabaseManager | None = None) -> None:
        self.database = database or DatabaseManager()
        self.settings = SettingsLoader()
        self.current_user_id: int | None = None

    def register(self, username: str, password: str) -> User:
        """Зарегистрировать пользователя и создать пустой портфель."""
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        users = self.database.load_users()
        if any(item["username"].casefold() == username.strip().casefold() for item in users):
            raise ValueError(f"Имя пользователя '{username}' уже занято")
        user_id = max((int(item["user_id"]) for item in users), default=0) + 1
        user = User.from_password(user_id, username, password)
        users.append(
            {
                "user_id": user.user_id,
                "username": user.username,
                "hashed_password": user.hashed_password,
                "salt": user.salt,
                "registration_date": user.registration_date.isoformat(),
            }
        )
        self.database.save_users(users)
        portfolios = self.database.load_portfolios()
        portfolios.append({"user_id": user_id, "wallets": {}})
        self.database.save_portfolios(portfolios)
        return user

    def login(self, username: str, password: str) -> User:
        """Проверить пароль и установить текущую сессию."""
        users = self.database.load_users()
        item = next((u for u in users if u["username"].casefold() == username.casefold()), None)
        if item is None:
            raise ValueError(f"Пользователь '{username}' не найден")
        user = self._user_from_record(item)
        if not user.verify_password(password):
            raise ValueError("Неверный пароль")
        self.current_user_id = user.user_id
        return user

    @staticmethod
    def _user_from_record(item: dict[str, Any]) -> User:
        return User(
            int(item["user_id"]),
            item["username"],
            item["hashed_password"],
            item["salt"],
            datetime.fromisoformat(item["registration_date"]),
        )

    def logout(self) -> None:
        """Завершить текущую сессию."""
        self.current_user_id = None

    def _require_user(self) -> User:
        if self.current_user_id is None:
            raise PermissionError("Сначала выполните login")
        item = next(
            (u for u in self.database.load_users() if int(u["user_id"]) == self.current_user_id),
            None,
        )
        if item is None:
            self.current_user_id = None
            raise PermissionError("Текущая сессия недействительна. Выполните login")
        return self._user_from_record(item)

    def _load_portfolio(self) -> Portfolio:
        user = self._require_user()
        records = self.database.load_portfolios()
        record = next((p for p in records if int(p["user_id"]) == user.user_id), None)
        if record is None:
            record = {"user_id": user.user_id, "wallets": {}}
            records.append(record)
            self.database.save_portfolios(records)
        wallets = {
            code: Wallet(code, data.get("balance", 0.0))
            for code, data in record.get("wallets", {}).items()
        }
        return Portfolio(user, wallets)

    def _save_portfolio(self, portfolio: Portfolio) -> None:
        records = self.database.load_portfolios()
        serialized = {
            code: {"currency_code": code, "balance": wallet.balance}
            for code, wallet in portfolio.wallets.items()
        }
        for record in records:
            if int(record["user_id"]) == portfolio.user_id:
                record["wallets"] = serialized
                break
        else:
            records.append({"user_id": portfolio.user_id, "wallets": serialized})
        self.database.save_portfolios(records)

    def _rates(self) -> dict:
        data = self.database.load_rates()
        if not data.get("pairs"):
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return {
                "pairs": {
                    code: {"rate": rate, "updated_at": now, "source": "demo"}
                    for code, rate in DEMO_RATES.items()
                },
                "last_refresh": now,
            }
        return data

    def deposit(self, currency_code: str, amount: float) -> tuple[float, float]:
        """Пополнить виртуальный кошелёк (служебная команда для демо)."""
        code = validate_currency_code(currency_code)
        amount = validate_amount(amount)
        portfolio = self._load_portfolio()
        wallet = portfolio.wallets.get(code) or portfolio.add_currency(code)
        before = wallet.balance
        wallet.deposit(amount)
        self._save_portfolio(portfolio)
        return before, wallet.balance

    @log_action("BUY", verbose=True)
    def buy(self, currency_code: str, amount: float) -> dict[str, Any]:
        """Купить amount единиц валюты, списав эквивалент с USD-кошелька."""
        code = validate_currency_code(currency_code)
        if code == "USD":
            raise ValueError("Для пополнения USD используйте команду deposit")
        amount = validate_amount(amount)
        rate = self.get_rate(code, "USD")
        cost = amount * rate["rate"]
        portfolio = self._load_portfolio()
        usd_wallet = portfolio.wallets.get("USD")
        if usd_wallet is None:
            raise ValueError(
                "USD-кошелёк пуст. Сначала выполните deposit --currency USD --amount ..."
            )
        if usd_wallet.balance + 1e-10 < cost:
            from valutatrade_hub.core.exceptions import InsufficientFundsError

            raise InsufficientFundsError(usd_wallet.balance, cost, "USD")
        target = portfolio.wallets.get(code) or portfolio.add_currency(code)
        before = target.balance
        usd_wallet.withdraw(cost)
        target.deposit(amount)
        self._save_portfolio(portfolio)
        return {
            "currency": code,
            "amount": amount,
            "rate": rate["rate"],
            "cost": cost,
            "before": before,
            "after": target.balance,
            "usd_balance": usd_wallet.balance,
        }

    @log_action("SELL", verbose=True)
    def sell(self, currency_code: str, amount: float) -> dict[str, Any]:
        """Продать amount единиц валюты и начислить эквивалент в USD."""
        code = validate_currency_code(currency_code)
        if code == "USD":
            raise ValueError("USD — расчётная валюта; для него используйте deposit")
        amount = validate_amount(amount)
        rate = self.get_rate(code, "USD")
        proceeds = amount * rate["rate"]
        portfolio = self._load_portfolio()
        try:
            wallet = portfolio.get_wallet(code)
        except KeyError as exc:
            raise ValueError(f"У вас нет кошелька '{code}'. Купите валюту командой buy.") from exc
        before = wallet.balance
        wallet.withdraw(amount)
        usd_wallet = portfolio.wallets.get("USD") or portfolio.add_currency("USD")
        usd_before = usd_wallet.balance
        usd_wallet.deposit(proceeds)
        self._save_portfolio(portfolio)
        return {
            "currency": code,
            "amount": amount,
            "rate": rate["rate"],
            "proceeds": proceeds,
            "before": before,
            "after": wallet.balance,
            "usd_before": usd_before,
            "usd_after": usd_wallet.balance,
        }

    def get_rate(self, from_code: str, to_code: str) -> dict[str, Any]:
        """Получить курс из кеша или учебной заглушки, проверив TTL."""
        source = validate_currency_code(from_code)
        target = validate_currency_code(to_code)
        get_currency(source)
        get_currency(target)
        cache = self._rates()
        rate = get_conversion_rate(source, target, cache)
        pairs = cache.get("pairs", {})
        key = f"{source}_{target}"
        reverse_key = f"{target}_{source}"
        record = pairs.get(key) or pairs.get(reverse_key)
        if record is None:
            record = {"updated_at": cache.get("last_refresh"), "source": "demo"}
        updated_at = record.get("updated_at") or cache.get("last_refresh")
        if updated_at:
            try:
                updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - updated).total_seconds()
                ttl = int(self.settings.get("RATES_TTL_SECONDS", 300))
                if age > ttl and record.get("source") != "demo":
                    raise ApiRequestError(
                        f"кеш курса {source}→{target} устарел. Выполните 'update-rates'"
                    )
            except ValueError:
                pass
        return {
            "from": source,
            "to": target,
            "rate": rate,
            "reverse_rate": 1.0 / rate,
            "updated_at": updated_at or "неизвестно",
            "source": record.get("source", "demo"),
        }

    def show_portfolio(self, base_currency: str = "USD") -> dict[str, Any]:
        """Подготовить данные портфеля для отображения CLI."""
        base = validate_currency_code(base_currency)
        portfolio = self._load_portfolio()
        rates = self._rates()
        rows = []
        total = 0.0
        for code, wallet in sorted(portfolio.wallets.items()):
            value = wallet.balance * get_conversion_rate(code, base, rates)
            rows.append({"currency": code, "balance": wallet.balance, "value": value})
            total += value
        return {
            "username": portfolio.user.username,
            "base": base,
            "rows": rows,
            "total": total,
        }
