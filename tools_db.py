"""SQLite tools for the dba_engineer agent (schema + read-only queries)."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager

from smolagents import tool

from paths import APP_DIR
from tools_files import _available, _resolve_upload

DB_PATH = APP_DIR / "app.db"
MAX_ROWS = 200


# ------- thread-safe connection
@contextmanager
def get_conn():
    """Yield a connection; guarantees close. Safe to call from any thread."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _rows_to_string(rows: list[sqlite3.Row], max_rows: int = MAX_ROWS) -> str:
    """Convert sqlite3.Row list -> readable string with column headers."""
    if not rows:
        return "(0 rows)"
    cols = rows[0].keys()
    lines = ["\t".join(cols)]
    for i, row in enumerate(rows):
        if i >= max_rows:
            lines.append(f"… ({len(rows) - max_rows} more rows truncated)")
            break
        lines.append("\t".join(str(row[c]) for c in cols))
    return "\n".join(lines)


@tool
def read_schema(filepath: str = "") -> str:
    """Read a .sql file and return the database SCHEMA (tables, columns,
    types, indexes, foreign keys). Does NOT execute any DML or DDL.

    If filepath is empty, returns the live schema from the database.

    Args:
        filepath: Optional .sql filename (e.g. "schema.sql") or path — bare
            filenames are looked up in uploads/, configs/ and the app dir.
    """
    parts: list[str] = []

    # a) If a file is given, extract CREATE TABLE / INDEX statements only
    if filepath:
        p = _resolve_upload(filepath)
        if p is None:
            return (
                f"ERROR: file not found: {filepath}. "
                f"Available files: {_available()}."
            )
        text = p.read_text(encoding="utf-8", errors="replace")
        # pull out DDL statements (CREATE …) — safe to show, never executed
        ddl = re.findall(
            r"(?:CREATE|ALTER)\s+(?:TABLE|INDEX|VIEW|TRIGGER)[\s\S]+?;",
            text,
            flags=re.IGNORECASE,
        )
        if ddl:
            parts.append(f"── DDL in {filepath} ──\n" + "\n\n".join(ddl[:20]))
        else:
            parts.append(f"(no CREATE/ALTER statements found in {filepath})")

    # b) Always include the live schema from DB
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL ORDER BY type, name"
        )
        rows = cur.fetchall()
        if rows:
            parts.append("── Live schema ──")
            for r in rows:
                parts.append(f"[{r['type']}] {r['name']}\n{r['sql']}\n")
        else:
            parts.append("(empty database)")

    return "\n".join(parts)


_SELECT_RE = re.compile(r"^\s*(SELECT|WITH|PRAGMA|EXPLAIN)\b", re.IGNORECASE)


@tool
def run_query(query: str) -> str:
    """Run a READ-ONLY SQL query and return the result as a table.

    Only SELECT, WITH (CTE), PRAGMA, and EXPLAIN are allowed.
    INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE are REJECTED.

    Args:
        query: A SQL SELECT statement, e.g.
            "SELECT id, name FROM users WHERE dept = 'eng' LIMIT 20"
    """
    # ── guard: only allow read-only verbs ──
    if not _SELECT_RE.match(query):
        return (
            "REJECTED: only SELECT / WITH / PRAGMA / EXPLAIN queries are allowed. "
            f"Got: {query[:120]}"
        )
    # extra safety: block common destructive keywords even inside subqueries
    forbidden = re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|ATTACH|DETACH)\b",
        query,
        re.IGNORECASE,
    )
    if forbidden:
        return f"REJECTED: contains forbidden keyword '{forbidden.group()}'. "

    with get_conn() as conn:
        cur = conn.execute(query)
        rows = cur.fetchall()
        return _rows_to_string(rows)
