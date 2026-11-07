"""Интерактивный CLI ValutaTrade Hub. Парсинг аргументов основан на shlex."""

import shlex

from prettytable import PrettyTable

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import UseCases
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


def _options(tokens: list[str]) -> dict[str, str]:
    """Преобразовать последовательность --key value в словарь."""
    result = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            raise ValueError(f"Неожиданный аргумент: {token}")
        key = token[2:]
        if index + 1 >= len(tokens) or tokens[index + 1].startswith("--"):
            result[key] = "true"
            index += 1
        else:
            result[key] = tokens[index + 1]
            index += 2
    return result


class CLI:
    """Тонкий слой: разбирает ввод, вызывает usecases и печатает результат."""

    def __init__(self) -> None:
        self.usecases = UseCases()

    def execute(self, line: str) -> bool:
        """Выполнить одну строку команды. Вернуть False для выхода."""
        try:
            tokens = shlex.split(line)
            if not tokens:
                return True
            command, *args = tokens
            if command in {"exit", "quit"}:
                print("До свидания!")
                return False
            if command in {"help", "--help"}:
                self._help()
                return True
            options = _options(args)
            handlers = {
                "register": self._register,
                "login": self._login,
                "logout": self._logout,
                "show-portfolio": self._show_portfolio,
                "buy": self._buy,
                "sell": self._sell,
                "get-rate": self._get_rate,
                "deposit": self._deposit,
                "update-rates": self._update_rates,
                "show-rates": self._show_rates,
            }
            handler = handlers.get(command)
            if handler is None:
                raise ValueError(f"Неизвестная команда '{command}'. Введите help")
            handler(options)
        except InsufficientFundsError as exc:
            print(str(exc))
        except CurrencyNotFoundError as exc:
            print(f"{exc}. Поддерживаемые коды: USD, EUR, GBP, RUB, BTC, ETH, SOL")
        except ApiRequestError as exc:
            print(f"{exc}. Проверьте сеть или выполните update-rates позже.")
        except (ValueError, TypeError, KeyError, PermissionError, RuntimeError) as exc:
            print(str(exc))
        except Exception as exc:  # защита CLI от непредвиденной ошибки
            print(f"Внутренняя ошибка: {exc}")
        return True

    @staticmethod
    def _required(options: dict, *names: str) -> list[str]:
        values = []
        for name in names:
            value = options.get(name)
            if value is None or value == "":
                raise ValueError(f"Обязательный аргумент --{name} не указан")
            values.append(value)
        return values

    def _register(self, options: dict) -> None:
        username, password = self._required(options, "username", "password")
        user = self.usecases.register(username, password)
        print(
            f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). Войдите: login --username {user.username} --password ****"
        )

    def _login(self, options: dict) -> None:
        username, password = self._required(options, "username", "password")
        user = self.usecases.login(username, password)
        print(f"Вы вошли как '{user.username}'")

    def _logout(self, options: dict) -> None:
        self.usecases.logout()
        print("Вы вышли из системы")

    def _show_portfolio(self, options: dict) -> None:
        base = options.get("base", "USD")
        data = self.usecases.show_portfolio(base)
        print(f"Портфель пользователя '{data['username']}' (база: {data['base']}):")
        if not data["rows"]:
            print("Портфель пуст. Пополните USD командой deposit или совершите первую операцию.")
            return
        table = PrettyTable(["Валюта", "Баланс", f"Стоимость, {data['base']}"])
        for row in data["rows"]:
            table.add_row([row["currency"], f"{row['balance']:.8f}", f"{row['value']:,.2f}"])
        print(table)
        print("-" * 42)
        print(f"ИТОГО: {data['total']:,.2f} {data['base']}")

    def _buy(self, options: dict) -> None:
        currency, amount = self._required(options, "currency", "amount")
        result = self.usecases.buy(currency, amount)
        print(
            f"Покупка выполнена: {result['amount']:.4f} {result['currency']} по курсу {result['rate']:,.4f} USD/{result['currency']}"
        )
        print(
            f"Изменения в портфеле: {result['currency']}: было {result['before']:.4f} → стало {result['after']:.4f}"
        )
        print(f"Списано: {result['cost']:,.2f} USD. Остаток USD: {result['usd_balance']:,.2f}")

    def _sell(self, options: dict) -> None:
        currency, amount = self._required(options, "currency", "amount")
        result = self.usecases.sell(currency, amount)
        print(
            f"Продажа выполнена: {result['amount']:.4f} {result['currency']} по курсу {result['rate']:,.4f} USD/{result['currency']}"
        )
        print(
            f"Изменения в портфеле: {result['currency']}: было {result['before']:.4f} → стало {result['after']:.4f}"
        )
        print(f"Оценочная выручка: {result['proceeds']:,.2f} USD")

    def _get_rate(self, options: dict) -> None:
        source, target = self._required(options, "from", "to")
        result = self.usecases.get_rate(source, target)
        print(
            f"Курс {result['from']}→{result['to']}: {result['rate']:.8g} (обновлено: {result['updated_at']}; источник: {result['source']})"
        )
        print(f"Обратный курс {result['to']}→{result['from']}: {result['reverse_rate']:.8g}")

    def _deposit(self, options: dict) -> None:
        currency, amount = self._required(options, "currency", "amount")
        before, after = self.usecases.deposit(currency, amount)
        print(f"Пополнение выполнено: {currency.upper()} было {before:.4f} → стало {after:.4f}")

    def _build_updater(self) -> RatesUpdater:
        config = ParserConfig()
        clients = [CoinGeckoClient(config), ExchangeRateApiClient(config)]
        storage = RatesStorage(config.RATES_FILE_PATH, config.HISTORY_FILE_PATH)
        return RatesUpdater(clients, storage)

    def _update_rates(self, options: dict) -> None:
        source = options.get("source")
        if source and source not in {"coingecko", "exchangerate"}:
            raise ValueError("--source должен быть coingecko или exchangerate")
        result = self._build_updater().run_update(source)
        if result["errors"]:
            print(f"Обновление завершено с ошибками. Загружено курсов: {result['updated']}")
            for error in result["errors"]:
                print(f"- {error}")
        else:
            print(
                f"Update successful. Total rates updated: {result['updated']}. Last refresh: {result['last_refresh']}"
            )

    def _show_rates(self, options: dict) -> None:
        settings = SettingsLoader()
        path = settings.path("RATES_FILE")
        import json

        if not path.exists():
            raise ValueError(
                "Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        pairs = data.get("pairs", {})
        if not pairs:
            raise ValueError(
                "Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные."
            )
        currency = options.get("currency", "").upper()
        base = options.get("base", "USD").upper()
        rows = []
        for pair, record in pairs.items():
            from_code, to_code = pair.split("_", 1)
            if currency and currency not in {from_code, to_code}:
                continue
            if to_code == base:
                value = record["rate"]
            elif from_code == base:
                value = 1 / record["rate"]
            else:
                continue
            rows.append(
                (
                    pair if base == to_code else f"{from_code}_{base}",
                    value,
                    record.get("updated_at", "-"),
                    record.get("source", "-"),
                )
            )
        top = options.get("top")
        if top:
            count = int(top)
            if count < 1:
                raise ValueError("--top должен быть положительным целым числом")
            rows = [
                r
                for r in sorted(rows, key=lambda item: item[1], reverse=True)
                if r[0].split("_")[0] in {"BTC", "ETH", "SOL"}
            ][:count]
        if not rows:
            raise ValueError(f"Курс для '{currency or base}' не найден в кеше.")
        print(f"Rates from cache (updated at {data.get('last_refresh', 'unknown')}):")
        table = PrettyTable(["Пара", f"Курс к {base}", "Обновлено", "Источник"])
        for row in sorted(rows, key=lambda item: item[0]):
            table.add_row([row[0], f"{row[1]:.8g}", row[2], row[3]])
        print(table)

    @staticmethod
    def _help() -> None:
        print("""Команды ValutaTrade Hub:
  register --username NAME --password PASS
  login --username NAME --password PASS
  logout
  deposit --currency USD --amount 10000   (виртуальное пополнение)
  show-portfolio [--base USD]
  buy --currency BTC --amount 0.05
  sell --currency BTC --amount 0.01
  get-rate --from BTC --to USD
  update-rates [--source coingecko|exchangerate]
  show-rates [--currency BTC] [--top 2] [--base USD]
  help | exit
""")


def main() -> None:
    """Точка входа интерактивного приложения."""
    settings = SettingsLoader()
    setup_logging(settings.get("LOG_LEVEL", "INFO"), settings.path("LOG_DIR"))
    cli = CLI()
    print("ValutaTrade Hub. Введите help для списка команд, exit для выхода.")
    while True:
        try:
            line = input("valutatrade> ")
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break
        if not cli.execute(line):
            break


if __name__ == "__main__":
    main()
