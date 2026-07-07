"""
Connection + schema-init helpers for the Revenue Engine System.

Plain stdlib sqlite3, no ORM. Every query anyone runs against this project
is either right here as a named helper or spelled out directly in
src/analytics/*.py -- there is no hidden query-generation layer, which is
the point (the brief explicitly asks to avoid black-box logic).
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "revenue_engine.db"
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"


def get_connection(db_path: Path = DB_PATH, check_same_thread: bool = True) -> sqlite3.Connection:
    """check_same_thread=False is for the read-only Streamlit UI layer only:
    Streamlit's st.cache_resource shares one cached connection object across
    the different worker threads it uses per session/rerun, which sqlite3
    rejects by default (`SQLite objects created in a thread can only be used
    in that same thread`). Safe here because src/ui/* never writes -- every
    scripts/*.py CLI entry point keeps the thread-safe default."""
    conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection, reset: bool = True) -> None:
    """(Re)create every table from db/schema.sql. reset=True drops existing
    tables first so re-running the seed generator is always idempotent."""
    if reset:
        # FK enforcement must be off for the drop phase -- dropping a parent
        # table (e.g. accounts) while foreign_keys=ON and children still
        # reference it raises errors depending on sqlite_master's drop order,
        # which is not guaranteed to be dependency-safe.
        conn.execute("PRAGMA foreign_keys = OFF")
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
    schema_sql = SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    conn.commit()


def insert_many(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    """Bulk-insert a list of dicts (all rows must share the same keys)."""
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(cols)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
    conn.commit()


def insert_one(conn: sqlite3.Connection, table: str, row: dict) -> int:
    cols = list(row.keys())
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(cols)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(row[c] for c in cols))
    conn.commit()
    return cur.lastrowid


def fetch_all(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[sqlite3.Row]:
    return conn.execute(query, params).fetchall()


def fetch_one(conn: sqlite3.Connection, query: str, params: tuple = ()) -> sqlite3.Row | None:
    return conn.execute(query, params).fetchone()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]
