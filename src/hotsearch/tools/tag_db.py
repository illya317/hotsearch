"""SQLite-backed tag database for keyword-based classification."""

import sqlite3
from pathlib import Path

from hotsearch import DATA_DIR

_DB_PATH: Path = DATA_DIR / "tags.db"


def get_db_path() -> Path:
    return _DB_PATH


def init_db() -> None:
    """Create tables and seed with TAG_RULES if empty."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_id INTEGER NOT NULL REFERENCES tags(id),
                keyword TEXT NOT NULL,
                weight INTEGER DEFAULT 10
            );
            CREATE INDEX IF NOT EXISTS idx_kw_tag ON keywords(tag_id);
            CREATE INDEX IF NOT EXISTS idx_kw_word ON keywords(keyword);
            """
        )
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM tags")
        if cur.fetchone()[0] == 0:
            from hotsearch.tools.tag import TAG_RULES

            for tag_name, keywords in TAG_RULES.items():
                cur.execute(
                    "INSERT INTO tags (name, description) VALUES (?, ?)",
                    (tag_name, ""),
                )
                tag_id = cur.lastrowid
                for kw in keywords:
                    cur.execute(
                        "INSERT INTO keywords (tag_id, keyword, weight) VALUES (?, ?, ?)",
                        (tag_id, kw, 10),
                    )
            conn.commit()
    finally:
        conn.close()


def _ensure_initialized() -> None:
    if not _DB_PATH.exists():
        init_db()
        return
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tags'"
        )
        if not cur.fetchone():
            init_db()
    finally:
        conn.close()


def classify(title: str) -> list[dict]:
    """Query all keywords and return matches as {tag_name, keyword, weight}."""
    _ensure_initialized()
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.name, k.keyword, k.weight
            FROM keywords k
            JOIN tags t ON t.id = k.tag_id
            """
        )
        title_lower = title.lower()
        matches: list[dict] = []
        for tag_name, keyword, weight in cur.fetchall():
            if keyword.lower() in title_lower:
                matches.append(
                    {"tag_name": tag_name, "keyword": keyword, "weight": weight}
                )
        return matches
    finally:
        conn.close()


def add_keyword(tag_name: str, keyword: str, weight: int = 10) -> None:
    """Add a keyword to a tag (create tag if it does not exist)."""
    _ensure_initialized()
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        row = cur.fetchone()
        if row:
            tag_id = row[0]
        else:
            cur.execute(
                "INSERT INTO tags (name, description) VALUES (?, ?)",
                (tag_name, ""),
            )
            tag_id = cur.lastrowid

        cur.execute(
            "INSERT OR IGNORE INTO keywords (tag_id, keyword, weight) VALUES (?, ?, ?)",
            (tag_id, keyword, weight),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_tags() -> list[str]:
    """Return all tag names."""
    _ensure_initialized()
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM tags ORDER BY name")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_keywords_for_tag(tag_name: str) -> list[dict]:
    """Return all keywords for a given tag."""
    _ensure_initialized()
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT k.keyword, k.weight
            FROM keywords k
            JOIN tags t ON t.id = k.tag_id
            WHERE t.name = ?
            ORDER BY k.keyword
            """,
            (tag_name,),
        )
        return [
            {"keyword": row[0], "weight": row[1]} for row in cur.fetchall()
        ]
    finally:
        conn.close()
