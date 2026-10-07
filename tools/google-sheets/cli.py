"""CLI для инструмента работы агента с Google Таблицами."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from client import load_environment  # noqa: E402
from sheets import GoogleSheetsTool  # noqa: E402


def print_json(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Инструмент для работы агента с Google Таблицами.")
    parser.add_argument("--credentials", help="Путь к JSON-ключу service account.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Создать новую Google Таблицу.")
    create.add_argument("--title", required=True)
    create.add_argument("--folder-id", default=os.getenv("GOOGLE_SHEETS_DRIVE_FOLDER_ID", ""))

    delete_file = subparsers.add_parser("delete-file", help="Удалить файл Google Таблицы.")
    delete_file.add_argument("spreadsheet")
    delete_file.add_argument(
        "--yes",
        action="store_true",
        help="Подтвердить удаление файла из Google Drive.",
    )

    rename_file = subparsers.add_parser("rename-file", help="Переименовать Google Таблицу.")
    rename_file.add_argument("spreadsheet")
    rename_file.add_argument("--title", required=True)

    ls = subparsers.add_parser("list", aliases=["ls"], help="Показать список листов.")
    ls.add_argument("spreadsheet")

    read = subparsers.add_parser("read", help="Прочитать первые строки листа.")
    read.add_argument("spreadsheet")
    read.add_argument("--worksheet")
    read.add_argument("--limit", type=int, default=5)

    write = subparsers.add_parser("write-csv", help="Записать CSV-файл в лист.")
    write.add_argument("spreadsheet")
    write.add_argument("--worksheet", required=True)
    write.add_argument("--csv", required=True)
    write.add_argument("--start-cell", default="A1")
    write.add_argument("--clear", action="store_true")
    write.add_argument("--chunk-size", type=int, default=5000)

    rename_sheet = subparsers.add_parser("rename-sheet", help="Переименовать лист.")
    rename_sheet.add_argument("spreadsheet")
    rename_sheet.add_argument("--worksheet", required=True)
    rename_sheet.add_argument("--title", required=True)

    delete_sheet = subparsers.add_parser("delete-sheet", help="Удалить один или несколько листов.")
    delete_sheet.add_argument("spreadsheet")
    delete_sheet.add_argument("--worksheet", action="append", required=True)
    delete_sheet.add_argument("--dry-run", action="store_true")

    reorder = subparsers.add_parser("reorder", help="Переставить листы в указанном порядке.")
    reorder.add_argument("spreadsheet")
    reorder.add_argument("--worksheet", action="append", required=True)

    return parser


def main() -> int:
    load_environment()
    args = build_parser().parse_args()
    tool = GoogleSheetsTool(credentials=args.credentials)

    if args.command == "create":
        result = tool.create_spreadsheet(
            title=args.title,
            folder_id=args.folder_id or None,
        )
    elif args.command == "delete-file":
        if not args.yes:
            raise SystemExit("Отказываюсь удалить таблицу без --yes.")
        result = tool.delete_spreadsheet(args.spreadsheet)
    elif args.command == "rename-file":
        result = tool.rename_spreadsheet(args.spreadsheet, args.title)
    elif args.command in {"list", "ls"}:
        result = [item.__dict__ for item in tool.list_worksheets(args.spreadsheet)]
    elif args.command == "read":
        result = tool.read_rows(
            args.spreadsheet,
            worksheet=args.worksheet,
            limit=args.limit,
        )
    elif args.command == "write-csv":
        result = tool.write_rows(
            args.spreadsheet,
            worksheet=args.worksheet,
            rows=read_csv_rows(Path(args.csv)),
            start_cell=args.start_cell,
            clear_existing=args.clear,
            chunk_size=args.chunk_size,
        )
    elif args.command == "rename-sheet":
        result = tool.rename_worksheet(
            args.spreadsheet,
            worksheet=args.worksheet,
            title=args.title,
        )
    elif args.command == "delete-sheet":
        result = tool.delete_worksheets(
            args.spreadsheet,
            worksheets=args.worksheet,
            dry_run=args.dry_run,
        )
    elif args.command == "reorder":
        result = tool.reorder_worksheets(args.spreadsheet, order=args.worksheet)
    else:  # pragma: no cover
        raise ValueError(f"Неизвестная команда: {args.command}")

    print_json(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
