"""SQLite research history (single user, local file)."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'data' / 'research_history.db'

_SCHEMA = '''CREATE TABLE IF NOT EXISTS research_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    report TEXT NOT NULL DEFAULT '',
    sources_json TEXT NOT NULL DEFAULT '[]',
    costs REAL NOT NULL DEFAULT 0,
    unverified_count INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    company_profile TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'market',
    registry_json TEXT NOT NULL DEFAULT ''
)'''
_SETTINGS_SCHEMA = 'CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)'


def _connect(db_path=None):
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.execute(_SETTINGS_SCHEMA)
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(research_runs)')}
    # Upgrade databases created before these fields existed.
    if 'company_profile' not in columns:
        conn.execute("ALTER TABLE research_runs ADD COLUMN company_profile TEXT NOT NULL DEFAULT ''")
    if 'mode' not in columns:
        conn.execute("ALTER TABLE research_runs ADD COLUMN mode TEXT NOT NULL DEFAULT 'market'")
    if 'registry_json' not in columns:
        conn.execute("ALTER TABLE research_runs ADD COLUMN registry_json TEXT NOT NULL DEFAULT ''")
    return conn


def save_run(topic, status, started_at, finished_at, result=None, error='', company_profile='', mode='market',
             db_path=None):
    """Store one research run and return its id."""
    with closing(_connect(db_path)) as conn, conn:
        cursor = conn.execute(
            'INSERT INTO research_runs (topic, status, started_at, finished_at, duration_seconds, report, '
            'sources_json, costs, unverified_count, error, company_profile, mode, registry_json) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (topic, status, started_at.isoformat(timespec='seconds'), finished_at.isoformat(timespec='seconds'),
             (finished_at - started_at).total_seconds(),
             result.report if result else '', json.dumps(result.sources if result else [], ensure_ascii=False),
             result.costs if result else 0.0, result.unverified_count if result else 0, error, company_profile, mode,
             json.dumps(result.registry, ensure_ascii=False) if result and getattr(result, 'registry', None) else ''))
        return cursor.lastrowid


def get_company_profile(db_path=None):
    with closing(_connect(db_path)) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'company_profile'").fetchone()
    return row['value'] if row else ''


def save_company_profile(profile, db_path=None):
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("INSERT INTO settings (key, value) VALUES ('company_profile', ?) "
                     'ON CONFLICT(key) DO UPDATE SET value = excluded.value', (profile,))


def list_runs(limit=100, db_path=None):
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            'SELECT id, topic, status, mode, started_at, finished_at, duration_seconds, unverified_count, '
            'json_array_length(sources_json) AS source_count FROM research_runs ORDER BY id DESC LIMIT ?',
            (limit,)).fetchall()
    return [dict(row) for row in rows]


def get_run(run_id, db_path=None):
    with closing(_connect(db_path)) as conn:
        row = conn.execute('SELECT * FROM research_runs WHERE id = ?', (run_id,)).fetchone()
    if row is None:
        return None
    run = dict(row)
    run['sources'] = json.loads(run.pop('sources_json'))
    registry_json = run.pop('registry_json')
    run['registry'] = json.loads(registry_json) if registry_json else None
    for key in ('started_at', 'finished_at'):
        run[key] = datetime.fromisoformat(run[key])
    return run


def delete_run(run_id, db_path=None):
    with closing(_connect(db_path)) as conn, conn:
        conn.execute('DELETE FROM research_runs WHERE id = ?', (run_id,))
