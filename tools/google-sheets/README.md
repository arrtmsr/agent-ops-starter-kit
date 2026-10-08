# Инструмент для Google Таблиц

Небольшой инструмент для агентов, которым нужно читать и писать данные в живые
Google Таблицы через Google Service Account.

Внутри нет проектных конфигов, имен клиентов, workflows и сложного
форматирования. Это базовый tool, который делает ключевые операции:

- открыть таблицу по ссылке или ID;
- быстро прочитать первые строки из листа для проверки доступа;
- прочитать конкретный диапазон в A1-формате;
- выгрузить большой лист в CSV батчами;
- записать CSV в лист чанками;
- создать новую Google Таблицу;
- переименовать таблицу;
- показать список листов;
- переименовать, удалить и переупорядочить листы;
- удалить файл Google Таблицы.

## Установка

```bash
pip install -r requirements.txt
```

## Ключ доступа

Создайте JSON-ключ Google Service Account и положите его в папку, которая не
попадает в git.

Пример структуры проекта:

```text
config/
  credentials/
    google/
      google-service-account.json
```

Затем создайте `.env`:

```text
GOOGLE_SHEETS_CREDENTIALS=config/credentials/google/google-service-account.json
```

Таблица должна быть расшарена на `client_email` из JSON-файла.

## Быстрая проверка

Прочитать первые 5 строк из первого листа. Это проверка доступа, а не
ограничение инструмента:

```bash
python tools/google-sheets/cli.py read "https://docs.google.com/spreadsheets/d/<ID>/edit" --limit 5
```

Прочитать конкретный лист:

```bash
python tools/google-sheets/cli.py read "<SPREADSHEET_URL>" --worksheet "Report" --limit 5
```

## Прочитать диапазон

Если нужно забрать конкретный кусок листа, используйте A1-диапазон:

```bash
python tools/google-sheets/cli.py read-range "<SPREADSHEET_URL>" \
  --worksheet "Report" \
  --range "A1:F100"
```

## Выгрузить лист батчами

Если данных много, не тяните весь лист одной операцией. Экспортируйте строки в
CSV батчами:

```bash
python tools/google-sheets/cli.py export-csv "<SPREADSHEET_URL>" \
  --worksheet "Report" \
  --output data/report.csv \
  --batch-size 5000
```

Можно ограничить объем чтения:

```bash
python tools/google-sheets/cli.py export-csv "<SPREADSHEET_URL>" \
  --worksheet "Report" \
  --output data/report-sample.csv \
  --max-rows 1000 \
  --max-columns 20
```

По умолчанию полностью пустые строки пропускаются. Если нужно сохранить их в
CSV, добавьте `--include-empty-rows`.

## Записать CSV

Записать CSV-файл в лист. Большие файлы пишутся чанками.

```bash
python tools/google-sheets/cli.py write-csv "<SPREADSHEET_URL>" \
  --worksheet "Digest" \
  --csv data/digest.csv \
  --clear
```

## Управление листами

```bash
python tools/google-sheets/cli.py list "<SPREADSHEET_URL>"

python tools/google-sheets/cli.py rename-sheet "<SPREADSHEET_URL>" \
  --worksheet "Sheet1" \
  --title "Raw data"

python tools/google-sheets/cli.py delete-sheet "<SPREADSHEET_URL>" \
  --worksheet "Old sheet" \
  --dry-run

python tools/google-sheets/cli.py reorder "<SPREADSHEET_URL>" \
  --worksheet "Summary" \
  --worksheet "Raw data"
```

## Управление файлом таблицы

```bash
python tools/google-sheets/cli.py create --title "Agent report"

python tools/google-sheets/cli.py rename-file "<SPREADSHEET_URL>" \
  --title "Agent report v2"

python tools/google-sheets/cli.py delete-file "<SPREADSHEET_URL>" --yes
```

`delete-file` удаляет файл из Google Drive. Для защиты команда требует `--yes`.
