"""Операции с живыми Google Таблицами.

Модуль специально небольшой: читать данные, писать данные чанками и управлять
листами. Для доступа используется JSON-ключ Google Service Account.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable

try:
    from .client import drive_service, gspread_client, service_account_credentials
except ImportError:  # Allows running cli.py as a direct script from google-sheets/.
    # Нужно для запуска `python tools/google-sheets/cli.py` из папки с дефисом.
    from client import drive_service, gspread_client, service_account_credentials


DEFAULT_CHUNK_SIZE = 5000
MAX_RETRIES = 3


def extract_spreadsheet_id(value: str) -> str:
    """Вернуть ID таблицы из полной ссылки Google Sheets или из уже готового ID."""
    value = value.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", value)
    if match:
        return match.group(1)
    return value


def spreadsheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


def _column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _normalize_rows(rows: Iterable[Iterable[Any]]) -> list[list[Any]]:
    normalized = []
    for row in rows:
        normalized.append(["" if value is None else value for value in row])
    return normalized


@dataclass
class SheetSummary:
    title: str
    sheet_id: int
    rows: int
    cols: int
    hidden: bool


class GoogleSheetsTool:
    """Небольшая обертка над gspread и Drive API для задач агента."""

    def __init__(self, credentials: str | None = None):
        self.credentials = credentials
        self.client = gspread_client(credentials)
        self.drive = drive_service(credentials)

    def open_spreadsheet(self, spreadsheet: str):
        return self.client.open_by_key(extract_spreadsheet_id(spreadsheet))

    def create_spreadsheet(
        self,
        *,
        title: str,
        folder_id: str | None = None,
    ) -> dict[str, str]:
        metadata: dict[str, object] = {
            "name": title,
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
        if folder_id:
            metadata["parents"] = [folder_id]
        created = (
            self.drive.files()
            .create(body=metadata, fields="id,name,mimeType,webViewLink")
            .execute()
        )
        spreadsheet_id = created["id"]
        return {
            "spreadsheet_id": spreadsheet_id,
            "title": created.get("name", title),
            "url": created.get("webViewLink") or spreadsheet_url(spreadsheet_id),
        }

    def delete_spreadsheet(self, spreadsheet: str) -> dict[str, Any]:
        spreadsheet_id = extract_spreadsheet_id(spreadsheet)
        self.drive.files().delete(fileId=spreadsheet_id).execute()
        return {"deleted": True, "spreadsheet_id": spreadsheet_id}

    def rename_spreadsheet(self, spreadsheet: str, title: str) -> dict[str, Any]:
        sheet = self.open_spreadsheet(spreadsheet)
        old_title = sheet.title
        sheet.batch_update(
            {
                "requests": [
                    {
                        "updateSpreadsheetProperties": {
                            "properties": {"title": title},
                            "fields": "title",
                        }
                    }
                ]
            }
        )
        return {
            "spreadsheet_id": extract_spreadsheet_id(spreadsheet),
            "old_title": old_title,
            "title": title,
            "url": spreadsheet_url(extract_spreadsheet_id(spreadsheet)),
        }

    def list_worksheets(self, spreadsheet: str) -> list[SheetSummary]:
        sheet = self.open_spreadsheet(spreadsheet)
        hidden_by_id: dict[int, bool] = {}
        metadata = sheet.fetch_sheet_metadata()
        for item in metadata.get("sheets", []):
            properties = item.get("properties", {})
            sheet_id = properties.get("sheetId")
            if sheet_id is not None:
                hidden_by_id[int(sheet_id)] = bool(properties.get("hidden", False))
        return [
            SheetSummary(
                title=worksheet.title,
                sheet_id=worksheet.id,
                rows=worksheet.row_count,
                cols=worksheet.col_count,
                hidden=hidden_by_id.get(worksheet.id, False),
            )
            for worksheet in sheet.worksheets()
        ]

    def read_rows(
        self,
        spreadsheet: str,
        *,
        worksheet: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        sheet = self.open_spreadsheet(spreadsheet)
        ws = sheet.worksheet(worksheet) if worksheet else sheet.get_worksheet(0)
        values = ws.get_all_values()
        return {
            "spreadsheet_id": extract_spreadsheet_id(spreadsheet),
            "worksheet": ws.title,
            "rows_returned": min(limit, len(values)),
            "rows": values[:limit],
        }

    def write_rows(
        self,
        spreadsheet: str,
        *,
        worksheet: str,
        rows: Iterable[Iterable[Any]],
        start_cell: str = "A1",
        clear_existing: bool = False,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        sheet = self.open_spreadsheet(spreadsheet)
        data = _normalize_rows(rows)
        if not data:
            raise ValueError("rows пустой")
        ws = self._get_or_create_worksheet(
            sheet,
            worksheet,
            rows=max(len(data) + 100, 1000),
            cols=max(max(len(row) for row in data), 26),
        )
        if clear_existing:
            ws.clear()

        chunks_written = 0
        if len(data) <= chunk_size:
            self._update_with_retry(
                ws,
                start_cell=start_cell,
                rows=data,
                value_input_option=value_input_option,
            )
            chunks_written = 1
        else:
            start_col, start_row = self._parse_cell(start_cell)
            for offset in range(0, len(data), chunk_size):
                chunk = data[offset : offset + chunk_size]
                chunk_start = f"{start_col}{start_row + offset}"
                self._update_with_retry(
                    ws,
                    start_cell=chunk_start,
                    rows=chunk,
                    value_input_option=value_input_option,
                )
                chunks_written += 1
        return {
            "spreadsheet_id": extract_spreadsheet_id(spreadsheet),
            "worksheet": ws.title,
            "rows_written": len(data),
            "chunks_written": chunks_written,
        }

    async def write_rows_async(
        self,
        spreadsheet: str,
        *,
        worksheet: str,
        rows: Iterable[Iterable[Any]],
        start_cell: str = "A1",
        clear_existing: bool = False,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        value_input_option: str = "USER_ENTERED",
        max_concurrent: int = 5,
    ) -> dict[str, Any]:
        """Асинхронная запись чанками для больших наборов данных.

        Параллельность держим умеренной. У Google Sheets API есть квоты, поэтому
        больше одновременных запросов не всегда лучше.
        """
        try:
            import asyncio
            import gspread
            import gspread_asyncio
        except ImportError as exc:
            raise RuntimeError(
                "Для асинхронной записи нужен gspread-asyncio. Запустите: "
                "pip install -r requirements.txt"
            ) from exc

        data = _normalize_rows(rows)
        if not data:
            raise ValueError("rows пустой")

        manager = gspread_asyncio.AsyncioGspreadClientManager(
            lambda: service_account_credentials(self.credentials)
        )
        client = await manager.authorize()
        sheet = await client.open_by_key(extract_spreadsheet_id(spreadsheet))
        try:
            ws = await sheet.worksheet(worksheet)
        except gspread.exceptions.WorksheetNotFound:
            ws = await sheet.add_worksheet(
                title=worksheet,
                rows=max(len(data) + 100, 1000),
                cols=max(max(len(row) for row in data), 26),
            )
        if clear_existing:
            await ws.clear()

        start_col, start_row = self._parse_cell(start_cell)
        semaphore = asyncio.Semaphore(max_concurrent)
        chunks = [
            (offset, data[offset : offset + chunk_size])
            for offset in range(0, len(data), chunk_size)
        ]

        async def write_chunk(offset: int, chunk: list[list[Any]]) -> None:
            async with semaphore:
                await ws.update(
                    f"{start_col}{start_row + offset}",
                    chunk,
                    value_input_option=value_input_option,
                )

        await asyncio.gather(*(write_chunk(offset, chunk) for offset, chunk in chunks))
        return {
            "spreadsheet_id": extract_spreadsheet_id(spreadsheet),
            "worksheet": worksheet,
            "rows_written": len(data),
            "chunks_written": len(chunks),
            "async": True,
        }

    def rename_worksheet(
        self,
        spreadsheet: str,
        *,
        worksheet: str,
        title: str,
    ) -> dict[str, Any]:
        sheet = self.open_spreadsheet(spreadsheet)
        ws = sheet.worksheet(worksheet)
        old_title = ws.title
        ws.update_title(title)
        return {"old_title": old_title, "title": title}

    def delete_worksheets(
        self,
        spreadsheet: str,
        *,
        worksheets: list[str],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        sheet = self.open_spreadsheet(spreadsheet)
        by_title = {worksheet.title: worksheet for worksheet in sheet.worksheets()}
        selected = [by_title[title] for title in worksheets if title in by_title]
        missing = [title for title in worksheets if title not in by_title]
        if len(selected) >= len(by_title):
            raise ValueError("Отказываюсь удалить все листы в таблице.")
        if not dry_run:
            for worksheet in selected:
                sheet.del_worksheet(worksheet)
        return {
            "deleted": [worksheet.title for worksheet in selected],
            "missing": missing,
            "dry_run": dry_run,
        }

    def reorder_worksheets(
        self,
        spreadsheet: str,
        *,
        order: list[str],
    ) -> dict[str, Any]:
        sheet = self.open_spreadsheet(spreadsheet)
        by_title = {worksheet.title: worksheet for worksheet in sheet.worksheets()}
        requests = []
        changed = []
        for index, title in enumerate(order):
            worksheet = by_title.get(title)
            if worksheet is None:
                continue
            changed.append(title)
            requests.append(
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": worksheet.id, "index": index},
                        "fields": "index",
                    }
                }
            )
        if requests:
            sheet.batch_update({"requests": requests})
        return {"reordered": changed}

    def _get_or_create_worksheet(self, spreadsheet, title: str, *, rows: int, cols: int):
        try:
            return spreadsheet.worksheet(title)
        except Exception:
            return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def _update_with_retry(
        self,
        worksheet,
        *,
        start_cell: str,
        rows: list[list[Any]],
        value_input_option: str,
    ) -> None:
        try:
            import gspread
        except ImportError as exc:
            raise RuntimeError("gspread не установлен") from exc

        for attempt in range(MAX_RETRIES):
            try:
                worksheet.update(
                    values=rows,
                    range_name=start_cell,
                    value_input_option=value_input_option,
                )
                return
            except gspread.exceptions.APIError as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status not in {429, 500, 503} or attempt == MAX_RETRIES - 1:
                    raise
                time.sleep((2**attempt) + random.uniform(0, 1))

    def _parse_cell(self, cell: str) -> tuple[str, int]:
        match = re.fullmatch(r"([A-Z]+)(\d+)", cell.strip().upper())
        if not match:
            return "A", 1
        return match.group(1), int(match.group(2))
