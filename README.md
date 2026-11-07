# Финальный проект по курсу "Программирование на Python"

Учебное консольное приложение на Python для регистрации пользователей, управления виртуальными валютными кошельками и симуляции покупки/продажи фиатных и криптовалют. Проект разделён на Core Service и Parser Service; данные Core Service хранятся в JSON.

## Требования

- Python 3.11 или новее
- [uv](https://docs.astral.sh/uv/)
- Для получения реальных курсов: API-ключ ExchangeRate-API (CoinGecko в базовом сценарии используется без ключа)

## Установка и запуск

```bash
uv sync
uv run valutatrade
```

Можно запустить без установки CLI-скрипта:

```bash
uv run python main.py
```

Проверки качества и тесты:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Пример полного сценария

```text
register --username alice --password 1234
login --username alice --password 1234
deposit --currency USD --amount 10000
get-rate --from BTC --to USD
buy --currency BTC --amount 0.05
show-portfolio
sell --currency BTC --amount 0.01
show-portfolio
logout
exit
```

Команда `deposit` добавлена как вспомогательная учебная команда: в исходном ТЗ нет способа пополнить начальный USD-кошелёк, без чего покупка с реальным списанием USD невозможна. Новый пользователь по-прежнему получает пустой портфель. Покупка списывает эквивалент в USD, продажа начисляет эквивалент в USD.

## Команды CLI

| Команда | Назначение |
|---|---|
| `register --username NAME --password PASS` | Регистрация и создание пустого портфеля |
| `login --username NAME --password PASS` | Вход в систему |
| `logout` | Завершение сессии |
| `show-portfolio [--base USD]` | Просмотр кошельков и общей стоимости |
| `deposit --currency USD --amount 10000` | Виртуальное пополнение кошелька |
| `buy --currency BTC --amount 0.05` | Покупка валюты за USD |
| `sell --currency BTC --amount 0.01` | Продажа валюты с зачислением USD |
| `get-rate --from BTC --to USD` | Получение прямого и обратного курса |
| `update-rates [--source coingecko|exchangerate]` | Запуск Parser Service вручную |
| `show-rates [--currency BTC] [--top 2] [--base USD]` | Просмотр кеша курсов |

Парсер принимает команды `update-rates` и `show-rates` в том же CLI. Текстовая оболочка разбирает аргументы через `shlex`, поэтому значения с пробелами можно заключать в кавычки.

## Архитектура

```text
valutatrade_hub/
├── core/
│   ├── currencies.py       # Currency, FiatCurrency, CryptoCurrency, реестр
│   ├── exceptions.py       # доменные исключения
│   ├── models.py           # User, Wallet, Portfolio
│   ├── usecases.py         # бизнес-сценарии Core Service
│   └── utils.py            # валидация и конвертация
├── infra/
│   ├── settings.py         # Singleton SettingsLoader
│   └── database.py         # Singleton DatabaseManager, JSON
├── parser_service/
│   ├── config.py           # настройки API и путей
│   ├── api_clients.py      # CoinGecko и ExchangeRate-API
│   ├── updater.py          # обновление нескольких источников
│   ├── storage.py          # кеш и история, атомарная запись
│   └── scheduler.py        # простой периодический запуск
├── cli/interface.py       # команды и пользовательский вывод
├── decorators.py          # @log_action
└── logging_config.py      # RotatingFileHandler
```

## JSON-хранилища

- `data/users.json` — пользователи, salted SHA-256-хеши и ISO-даты регистрации. Открытые пароли не сохраняются.
- `data/portfolios.json` — кошельки пользователей и балансы.
- `data/rates.json` — последний снимок: `pairs`, `rate`, `updated_at`, `source`, `last_refresh`.
- `data/exchange_rates.json` — история успешных измерений с уникальным `id`.

Запись JSON выполняется через временный файл и `os.replace`. В `SettingsLoader` настраиваются пути, базовая валюта, TTL (по умолчанию 300 секунд) и директория логов. При чтении старого кеша Core Service проверяет TTL; если курс устарел, приложение предлагает выполнить `update-rates`.

## Parser Service и API-ключ

CoinGecko используется для криптовалют, ExchangeRate-API — для фиатных. Ключ не хранится в коде. В Linux/macOS перед запуском задайте переменную окружения:

```bash
export EXCHANGERATE_API_KEY="ваш_ключ"
uv run valutatrade
```

В PowerShell:

```powershell
$env:EXCHANGERATE_API_KEY = "ваш_ключ"
uv run valutatrade
```

Затем выполните `update-rates`. Если один источник недоступен, `RatesUpdater` запишет успешно полученные данные второго источника и сообщит об ошибке первого. Без сети и ключа Core Service может работать на учебных курсах-заглушках из задания; источник будет помечен как `demo`. Не используйте демонстрационные значения для реальных финансовых решений.

## Логирование

- `logs/actions.log` — BUY/SELL и доменные операции.
- `logs/parser.log` — обновление курсов и ошибки API.
- Уровень по умолчанию — INFO; ротация — 1 МБ, три резервных файла.
- Декоратор `@log_action` пишет результат операции и повторно выбрасывает исходное исключение.

## Демонстрация

[![asciicast](https://asciinema.org/a/P6Jhbt43iG8NRfzk.svg)](https://asciinema.org/a/P6Jhbt43iG8NRfzk)
