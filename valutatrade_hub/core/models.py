"""Модели пользователя, кошелька и портфеля."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Any

from valutatrade_hub.core.exceptions import InsufficientFundsError


def _password_hash(password: str, salt: str) -> str:
    """Вычислить SHA-256-хеш пароля с солью (учебная реализация из ТЗ)."""
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


class User:
    """Зарегистрированный пользователь системы."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        if not isinstance(user_id, int) or user_id < 1:
            raise ValueError("user_id должен быть положительным целым числом")
        self._user_id = user_id
        self.username = username
        if not hashed_password or not salt:
            raise ValueError("Хеш пароля и соль обязательны")
        self._hashed_password = hashed_password
        self._salt = salt
        if isinstance(registration_date, str):
            registration_date = datetime.fromisoformat(registration_date)
        if not isinstance(registration_date, datetime):
            raise TypeError("registration_date должен быть datetime")
        self._registration_date = registration_date

    @classmethod
    def from_password(cls, user_id: int, username: str, password: str) -> "User":
        """Создать пользователя, самостоятельно сформировав соль и хеш."""
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        salt = secrets.token_hex(16)
        return cls(
            user_id, username, _password_hash(password, salt), salt, datetime.now().astimezone()
        )

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        """Хеш для сериализации; исходный пароль никогда не возвращается."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def get_user_info(self) -> dict[str, Any]:
        """Вернуть безопасную информацию без хеша и соли."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Заменить пароль, создав новую соль и новый хеш."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._salt = secrets.token_hex(16)
        self._hashed_password = _password_hash(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Проверить пароль без раскрытия хеша."""
        if not isinstance(password, str):
            return False
        candidate = _password_hash(password, self._salt)
        return hmac.compare_digest(candidate, self._hashed_password)


class Wallet:
    """Кошелёк для одной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        self.currency_code = currency_code.strip().upper()
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    @staticmethod
    def _validate_amount(amount: float) -> float:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом")
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        return float(amount)

    def deposit(self, amount: float) -> None:
        """Пополнить кошелёк на положительную сумму."""
        self._balance += self._validate_amount(amount)

    def withdraw(self, amount: float) -> None:
        """Снять средства, если остаток это позволяет."""
        amount = self._validate_amount(amount)
        if amount > self._balance + 1e-10:
            raise InsufficientFundsError(self._balance, amount, self.currency_code)
        self._balance = max(0.0, self._balance - amount)

    def get_balance_info(self) -> str:
        """Вернуть строку с валютой и текущим балансом."""
        return f"{self.currency_code}: {self._balance:.8f}"


class Portfolio:
    """Все валютные кошельки одного пользователя."""

    def __init__(self, user: User, wallets: dict[str, Wallet] | None = None) -> None:
        if not isinstance(user, User):
            raise TypeError("user должен быть объектом User")
        self._user = user
        self._wallets: dict[str, Wallet] = {}
        for code, wallet in (wallets or {}).items():
            if not isinstance(wallet, Wallet):
                raise TypeError("Все значения wallets должны быть объектами Wallet")
            self._wallets[code.upper()] = wallet

    @property
    def user(self) -> User:
        return self._user

    @property
    def user_id(self) -> int:
        return self._user.user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Вернуть копию словаря (сами объекты Wallet остаются рабочими)."""
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> Wallet:
        """Создать кошелёк, если его ещё нет."""
        code = currency_code.strip().upper()
        if code in self._wallets:
            raise ValueError(f"Кошелёк '{code}' уже существует")
        wallet = Wallet(code)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet:
        """Получить кошелёк или понятную ошибку."""
        code = currency_code.strip().upper()
        try:
            return self._wallets[code]
        except KeyError as exc:
            raise KeyError(f"У вас нет кошелька '{code}'") from exc

    def get_total_value(self, base_currency: str = "USD", rates: dict | None = None) -> float:
        """Посчитать суммарную стоимость портфеля в базовой валюте."""
        from valutatrade_hub.core.utils import convert_amount

        return sum(
            convert_amount(wallet.balance, code, base_currency, rates or {})
            for code, wallet in self._wallets.items()
        )
