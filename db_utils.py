import sqlite3
import csv
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

DB_PATH = "leads.db"
CSV_PATH = "leads.csv"


def init_db() -> bool:
    """Initialize SQLite database for leads and sessions."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT NOT NULL,
                service TEXT,
                best_time TEXT,
                details TEXT,
                ip_address TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT,
                history TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        logger.info("SQLite database initialized successfully.")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False


def save_lead(lead_data: dict, ip_address: str = "unknown") -> bool:
    """Save lead data to SQLite and leads.csv."""
    name = lead_data.get("name")
    email = lead_data.get("email")

    if not name or not email:
        logger.warning("Attempted to save lead with missing name or email.")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO leads (name, phone, email, service, best_time, details, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                name,
                lead_data.get("phone"),
                email,
                lead_data.get("service"),
                lead_data.get("best_time"),
                lead_data.get("details"),
                ip_address,
            ),
        )
        conn.commit()
        conn.close()
        logger.info(f"Lead from {name} saved to SQLite.")
    except Exception as e:
        logger.error(f"Error saving lead to SQLite: {e}")

    csv_exists = Path(CSV_PATH).exists()
    fields = [
        "timestamp",
        "name",
        "phone",
        "email",
        "service",
        "best_time",
        "details",
        "ip_address",
    ]

    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if not csv_exists:
                writer.writeheader()

            writer.writerow(
                {
                    "timestamp": datetime.now().isoformat(),
                    "name": name,
                    "phone": lead_data.get("phone"),
                    "email": email,
                    "service": lead_data.get("service"),
                    "best_time": lead_data.get("best_time"),
                    "details": lead_data.get("details"),
                    "ip_address": ip_address,
                }
            )
        logger.info(f"Lead from {name} appended to CSV.")
    except Exception as e:
        logger.error(f"Error saving lead to CSV: {e}")

    return True


def get_lead_count_per_ip(ip_address: str, hours: int = 24) -> int:
    """Get number of leads from a specific IP in the last X hours for rate limiting."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM leads 
            WHERE ip_address = ? AND timestamp > datetime('now', ?)
        """,
            (ip_address, f"-{hours} hours"),
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Error checking IP lead count: {e}")
        return 0


def save_session_history(session_id: str, history: list, title: str = None) -> bool:
    """Save conversation history and optional title to SQLite."""
    try:
        import json

        history_json = json.dumps(history)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if title:
            cursor.execute(
                """
                INSERT INTO sessions (session_id, title, history, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    title = excluded.title,
                    history = excluded.history,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (session_id, title, history_json),
            )
        else:
            cursor.execute(
                """
                INSERT INTO sessions (session_id, history, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    history = excluded.history,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (session_id, history_json),
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving session history: {e}")
        return False


def get_all_sessions() -> list:
    """Retrieve all session IDs and titles from SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Ensure the table exists even if this is called first
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
        )
        if not cursor.fetchone():
            conn.close()
            return []

        # Check if 'title' column exists (migration)
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [col[1] for col in cursor.fetchall()]
        if "title" not in columns:
            logger.info("Migrating sessions table: adding 'title' column")
            cursor.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
            conn.commit()

        cursor.execute(
            "SELECT session_id, title, updated_at FROM sessions ORDER BY updated_at DESC"
        )
        rows = cursor.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            sid = row[0]
            title = row[1] or f"Chat {sid[:8]}"
            sessions.append({"id": sid, "title": title, "updated_at": row[2]})
        return sessions
    except Exception as e:
        logger.error(f"Error getting all sessions: {e}")
        return []


def get_session_history(session_id: str) -> list:
    """Retrieve conversation history from SQLite."""
    try:
        import json

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT history FROM sessions WHERE session_id = ?", (session_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return []
    except Exception as e:
        logger.error(f"Error getting session history: {e}")
        return []


def check_db_connection() -> bool:
    """Check if database is connected and accessible."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        return True
    except Exception:
        return False
