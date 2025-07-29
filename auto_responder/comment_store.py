import sqlite3
from datetime import datetime

DB_FILE = "comments.db"


# Initialize the SQLite database for storing comments and posts
def init_comment_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            post_id TEXT PRIMARY KEY,
            page_id TEXT,
            brand_name TEXT,
            created_time TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            comment_id TEXT PRIMARY KEY,
            user_id TEXT,
            page_id TEXT,
            post_id TEXT,
            brand_name TEXT,
            message TEXT,
            created_time TEXT,
            responded INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


# Insert or update post records in the database
def log_post(post_id, page_id, brand_name, created_time):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO posts (post_id, page_id, brand_name, created_time)
        VALUES (?, ?, ?, ?)
    """, (post_id, page_id, brand_name, created_time))
    conn.commit()
    conn.close()


# Insert or update comment records in the database
def log_comment(comment_id, user_id, page_id, post_id, brand_name, message, created_time):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO comments (comment_id, user_id, page_id, post_id, brand_name, message, created_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (comment_id, user_id, page_id, post_id, brand_name, message, created_time))
    conn.commit()
    conn.close()


# Update an existing comment record to mark it as responded
def mark_comment_as_responded(comment_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE comments SET responded = 1 WHERE comment_id = ?", (comment_id,))
    conn.commit()
    conn.close()


# Retrieve latest N comments for a specific post
def get_recent_post_comments(post_id, page_id, limit=5):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message FROM comments
        WHERE post_id = ? AND page_id = ?
        ORDER BY created_time DESC
        LIMIT ?
    """, (post_id, page_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in reversed(rows)]
