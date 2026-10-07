# Agent Ops Starter Kit

Стартовый набор инструментов для агентских сценариев, которым нужно безопасно
работать с Google Sheets через Google Service Account.

Сейчас в репозитории есть CLI-инструмент для Google Таблиц. Он умеет создавать
таблицы, читать первые строки, записывать CSV, управлять листами и удалять
таблицы через Google Drive API.

## Что внутри

```text
tools/google-sheets/
  cli.py       # CLI-команды
  client.py    # загрузка окружения и подключение к Google API
  sheets.py    # операции с таблицами и листами

.env.example   # пример переменных окружения без секретов
.gitignore     # правила, чтобы credentials не попадали в git
requirements.txt
```

## Безопасность credentials

JSON-ключ сервисного аккаунта не должен попадать в репозиторий. Для этого в
`.gitignore` уже добавлены правила для:

- `.env` и локальных `.env.*` файлов;
- `config/credentials/`, `credentials/`, `secrets/`;
- `*-service-account.json`, `*service_account*.json`, `*credentials*.json`;
- ключей `*.pem`, `*.p12`, `*.key`.

Рекомендуемая локальная структура:

```text
config/
  credentials/
    google/
      google-service-account.json
```

## Подготовка Google Cloud

Тестовые значения для sandbox-проекта:

- Project name: `Agent Ops Sandbox`
- Project ID: `agent-ops-sandbox-2026`
- Service account name: `Agent Ops Service Account`
- Service account ID: `agent-ops-service-account`

В Google Cloud нужно:

1. Создать или выбрать проект.
2. Включить Google Sheets API и Google Drive API.
3. Создать Service Account.
4. Создать JSON-ключ для Service Account и положить его локально в
   `config/credentials/google/google-service-account.json`.
5. Расшарить нужную Google Таблицу или папку Drive на `client_email` из JSON-ключа.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Настройка окружения

Создайте локальный `.env` из примера:

```bash
cp .env.example .env
```

Основная переменная:

```text
GOOGLE_SHEETS_CREDENTIALS=config/credentials/google/google-service-account.json
```

Дополнительно можно задать значения по умолчанию:

```text
GOOGLE_SHEETS_SPREADSHEET=
GOOGLE_SHEETS_WORKSHEET=
GOOGLE_SHEETS_DRIVE_FOLDER_ID=
```

## Примеры команд

Создать новую таблицу:

```bash
python tools/google-sheets/cli.py create --title "Agent report"
```

Показать список листов:

```bash
python tools/google-sheets/cli.py list "<SPREADSHEET_URL_OR_ID>"
```

Прочитать первые 5 строк:

```bash
python tools/google-sheets/cli.py read "<SPREADSHEET_URL_OR_ID>" --limit 5
```

Записать CSV в лист:

```bash
python tools/google-sheets/cli.py write-csv "<SPREADSHEET_URL_OR_ID>" \
  --worksheet "Digest" \
  --csv data/digest.csv \
  --clear
```

Переименовать лист:

```bash
python tools/google-sheets/cli.py rename-sheet "<SPREADSHEET_URL_OR_ID>" \
  --worksheet "Sheet1" \
  --title "Raw data"
```

Удалить таблицу из Google Drive:

```bash
python tools/google-sheets/cli.py delete-file "<SPREADSHEET_URL_OR_ID>" --yes
```

## Проверка перед коммитом

Перед публикацией убедитесь, что секреты не попали в индекс:

```bash
git status --short
git check-ignore -v .env config/credentials/google/google-service-account.json
```

В репозиторий должны попадать только шаблоны и код, например `.env.example`, но
не `.env` и не JSON-ключи сервисных аккаунтов.
