"""Общие помощники для подключения к Google Sheets и Google Drive."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[2]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]


def load_environment() -> None:
    """Загрузить `.env` из корня проекта, если установлен python-dotenv."""
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")


def credentials_path(path: str | None = None) -> Path:
    """Найти путь к JSON-ключу service account."""
    raw = (
        path
        or os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        or os.getenv("GOOGLE_DRIVE_CREDENTIALS")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or "config/credentials/google/google-service-account.json"
    )
    resolved = Path(raw)
    if not resolved.is_absolute():
        resolved = ROOT / resolved
    return resolved


def service_account_credentials(path: str | None = None):
    try:
        from google.oauth2.service_account import Credentials
    except ImportError as exc:
        raise RuntimeError(
            "Библиотеки Google Auth не установлены. Запустите: "
            "pip install -r requirements.txt"
        ) from exc

    resolved = credentials_path(path)
    if not resolved.exists():
        raise FileNotFoundError(
            f"Google credentials not found: {resolved}. "
            "Укажите GOOGLE_SHEETS_CREDENTIALS или передайте --credentials."
        )
    return Credentials.from_service_account_file(str(resolved), scopes=SCOPES)


def gspread_client(path: str | None = None):
    try:
        import gspread
    except ImportError as exc:
        raise RuntimeError(
            "gspread не установлен. Запустите: "
            "pip install -r requirements.txt"
        ) from exc

    return gspread.authorize(service_account_credentials(path))


def drive_service(path: str | None = None):
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "google-api-python-client не установлен. Запустите: "
            "pip install -r requirements.txt"
        ) from exc

    return build("drive", "v3", credentials=service_account_credentials(path))
