import os
import json
import sqlite3
import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "email_assistant.db")

def get_connection():
    """Get thread-safe SQLite connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Emails Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            subject TEXT,
            body TEXT NOT NULL,
            is_spam INTEGER DEFAULT 0,
            spam_confidence REAL DEFAULT 0.0,
            category TEXT DEFAULT 'Personal',
            urgency TEXT DEFAULT 'Medium',
            sentiment TEXT DEFAULT 'Neutral',
            action_items TEXT DEFAULT '[]',
            reply TEXT DEFAULT '',
            status TEXT DEFAULT 'Processed',
            source TEXT DEFAULT 'mock',
            created_at TEXT NOT NULL
        )
    """)

    # Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT DEFAULT 'INFO',
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

def log_event(level: str, message: str):
    """Log an operational event to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO system_logs (level, message, created_at) VALUES (?, ?, ?)",
        (level.upper(), message, now)
    )
    conn.commit()
    conn.close()

def insert_email(email_data: Dict[str, Any]) -> int:
    """Insert a processed email record."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = email_data.get("created_at") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    action_items_str = email_data.get("action_items")
    if isinstance(action_items_str, (list, tuple)):
        action_items_str = json.dumps(action_items_str)
    elif not action_items_str:
        action_items_str = "[]"

    cursor.execute("""
        INSERT INTO emails (
            sender, subject, body, is_spam, spam_confidence, category,
            urgency, sentiment, action_items, reply, status, source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        email_data.get("sender", "Unknown Sender"),
        email_data.get("subject", "No Subject"),
        email_data.get("body", ""),
        1 if email_data.get("is_spam") else 0,
        float(email_data.get("spam_confidence", 0.0)),
        email_data.get("category", "Personal"),
        email_data.get("urgency", "Medium"),
        email_data.get("sentiment", "Neutral"),
        action_items_str,
        email_data.get("reply", ""),
        email_data.get("status", "Processed"),
        email_data.get("source", "mock"),
        now
    ))
    
    email_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return email_id

def get_emails(
    limit: int = 50,
    is_spam: Optional[bool] = None,
    category: Optional[str] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve emails with optional filters."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM emails WHERE 1=1"
    params = []

    if is_spam is not None:
        query += " AND is_spam = ?"
        params.append(1 if is_spam else 0)

    if category and category != "All":
        query += " AND category = ?"
        params.append(category)

    if search:
        query += " AND (subject LIKE ? OR body LIKE ? OR sender LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    results = []
    for r in rows:
        d = dict(r)
        d["is_spam"] = bool(d["is_spam"])
        try:
            d["action_items"] = json.loads(d["action_items"])
        except:
            d["action_items"] = []
        results.append(d)
        
    conn.close()
    return results

def get_email_by_id(email_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single email by its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["is_spam"] = bool(d["is_spam"])
        try:
            d["action_items"] = json.loads(d["action_items"])
        except:
            d["action_items"] = []
        return d
    return None

def update_email_status(email_id: int, status: str, reply: Optional[str] = None) -> bool:
    """Update status and optionally the reply text for an email."""
    conn = get_connection()
    cursor = conn.cursor()
    if reply is not None:
        cursor.execute(
            "UPDATE emails SET status = ?, reply = ? WHERE id = ?",
            (status, reply, email_id)
        )
    else:
        cursor.execute(
            "UPDATE emails SET status = ? WHERE id = ?",
            (status, email_id)
        )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def delete_email(email_id: int) -> bool:
    """Delete an email by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emails WHERE id = ?", (email_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_analytics_stats() -> Dict[str, Any]:
    """Calculate aggregated analytics for dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM emails")
    total_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM emails WHERE is_spam = 1")
    spam_count = cursor.fetchone()[0]

    ham_count = total_count - spam_count
    spam_percentage = (spam_count / total_count * 100) if total_count > 0 else 0.0

    # Category breakdown
    cursor.execute("SELECT category, COUNT(*) FROM emails GROUP BY category")
    category_rows = cursor.fetchall()
    categories = {row[0]: row[1] for row in category_rows}

    # Urgency breakdown
    cursor.execute("SELECT urgency, COUNT(*) FROM emails WHERE is_spam = 0 GROUP BY urgency")
    urgency_rows = cursor.fetchall()
    urgencies = {row[0]: row[1] for row in urgency_rows}

    # Status breakdown
    cursor.execute("SELECT status, COUNT(*) FROM emails GROUP BY status")
    status_rows = cursor.fetchall()
    statuses = {row[0]: row[1] for row in status_rows}

    # Drafted replies count
    cursor.execute("SELECT COUNT(*) FROM emails WHERE reply != '' AND is_spam = 0")
    replies_count = cursor.fetchone()[0]

    conn.close()

    return {
        "total_emails": total_count,
        "spam_count": spam_count,
        "ham_count": ham_count,
        "spam_percentage": round(spam_percentage, 1),
        "replies_count": replies_count,
        "categories": categories,
        "urgencies": urgencies,
        "statuses": statuses
    }

# Initialize on import
init_db()
