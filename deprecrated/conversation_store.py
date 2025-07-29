import sqlite3
from datetime import datetime

DB_FILE = "conversations.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            page_id TEXT,
            brand_name TEXT,
            message TEXT,
            created_time TEXT,
            responded INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def log_message(msg_id, user_id, page_id, brand_name, text, created_time):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO messages (id, user_id, page_id, brand_name, message, created_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (msg_id, user_id, page_id, brand_name, text, created_time))
        conn.commit()
    finally:
        conn.close()


def mark_as_responded(msg_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET responded = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()


def get_recent_user_messages(user_id, page_id, limit=5):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message FROM messages
        WHERE user_id = ? AND page_id = ?
        ORDER BY created_time DESC
        LIMIT ?
    """, (user_id, page_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in reversed(rows)]  # reverse to get oldest → newest


# Test it
if __name__ == "__main__":
    init_db()
    log_message("m_1234", "user_1", "page_1", "Vitris Supplements", "What do you sell?", datetime.utcnow().isoformat())
    print(get_recent_user_messages("user_1", "page_1"))
