"""Back up the SQLite history database to Supabase Storage, so the cloud app keeps its data across restarts.

Streamlit Community Cloud empties the local file system when the app restarts. When SUPABASE_URL and
SUPABASE_SERVICE_KEY are set, the database file is downloaded once at startup and uploaded after every write.
"""
import logging
import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import httpx

import history

SETTING_NAMES = ('SUPABASE_URL', 'SUPABASE_SERVICE_KEY', 'SUPABASE_BUCKET')
DEFAULT_BUCKET = 'gntc'
OBJECT_NAME = 'research_history.db'
TIMEOUT_SECONDS = 30
_SQLITE_HEADER = b'SQLite format 3\x00'
_LOCK = threading.Lock()
last_backup_ok = True


def configured():
    return bool(os.getenv('SUPABASE_URL', '').strip() and os.getenv('SUPABASE_SERVICE_KEY', '').strip())


def _object_url():
    bucket = os.getenv('SUPABASE_BUCKET', '').strip() or DEFAULT_BUCKET
    return f'{os.environ["SUPABASE_URL"].strip().rstrip("/")}/storage/v1/object/{bucket}/{OBJECT_NAME}'


def _headers():
    key = os.environ['SUPABASE_SERVICE_KEY'].strip()
    return {'Authorization': f'Bearer {key}', 'apikey': key}


def _is_missing(response):
    # Supabase Storage answers a missing object with 404, or with 400 and {"statusCode": "404"}.
    if response.status_code == 404:
        return True
    try:
        return response.status_code == 400 and str(response.json().get('statusCode')) == '404'
    except ValueError:
        return False


def start(db_path=None, client=None):
    """Restore the backup, then back up after every write. Returns 'off', 'restored', 'new' or 'error'.

    On 'error' nothing is ever uploaded, so a failed download cannot overwrite the backup with an empty database.
    """
    if not configured():
        return 'off'
    target = Path(db_path or history.DB_PATH)
    try:
        response = (client or httpx).get(_object_url(), headers=_headers(), timeout=TIMEOUT_SECONDS)
        if _is_missing(response):
            state = 'new'
        else:
            response.raise_for_status()
            if not response.content.startswith(_SQLITE_HEADER):
                raise ValueError('backup is not a SQLite database')
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix('.download')
            partial.write_bytes(response.content)
            partial.replace(target)
            state = 'restored'
    except (httpx.HTTPError, ValueError, OSError) as exc:
        # Do not echo the exception text: it can contain the request headers.
        logging.getLogger('gntc').warning('Supabase 還原失敗（%s），本次不備份', type(exc).__name__)
        return 'error'
    history.on_write = lambda path: backup(target, client) if Path(path).resolve() == target.resolve() else None
    return state


def backup(db_path, client=None):
    """Upload a consistent snapshot of the database. Never raises: the data is still saved locally."""
    global last_backup_ok
    with _LOCK:
        try:
            with closing(sqlite3.connect(db_path)) as conn:
                data = conn.serialize()
            response = (client or httpx).post(
                _object_url(), content=data, timeout=TIMEOUT_SECONDS,
                headers={**_headers(), 'x-upsert': 'true', 'Content-Type': 'application/octet-stream'})
            response.raise_for_status()
        except (httpx.HTTPError, sqlite3.Error) as exc:
            logging.getLogger('gntc').warning('Supabase 備份失敗（%s）', type(exc).__name__)
            last_backup_ok = False
            return False
    last_backup_ok = True
    return True
