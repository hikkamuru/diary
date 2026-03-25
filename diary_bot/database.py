import sqlite3
from datetime import datetime
from config import DB_PATH


class DiaryDatabase:
    def __init__(self):
        self.db_path = DB_PATH
        self.conn = None
        self.cursor = None
        self.create_tables()
    
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def create_tables(self):
        self.connect()
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS diary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_diary_user_date 
            ON diary_entries(user_id, entry_date)
        ''')
        
        self.conn.commit()
        self.close()
    
    def add_entry(self, user_id, content, entry_date):
        self.connect()
        self.cursor.execute('''
            INSERT INTO diary_entries (user_id, content, entry_date)
            VALUES (?, ?, ?)
        ''', (user_id, content, entry_date))
        self.conn.commit()
        self.close()
    
    def get_entries(self, user_id, limit=30):
        self.connect()
        self.cursor.execute('''
            SELECT id, content, entry_date, created_at
            FROM diary_entries
            WHERE user_id = ?
            ORDER BY entry_date DESC, created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        entries = self.cursor.fetchall()
        self.close()
        return entries
    
    def get_entry_by_date(self, user_id, entry_date):
        self.connect()
        self.cursor.execute('''
            SELECT id, content, entry_date, created_at
            FROM diary_entries
            WHERE user_id = ? AND entry_date = ?
            ORDER BY created_at DESC
        ''', (user_id, entry_date))
        entries = self.cursor.fetchall()
        self.close()
        return entries
    
    def delete_entry(self, user_id, entry_id):
        self.connect()
        self.cursor.execute('''
            DELETE FROM diary_entries
            WHERE id = ? AND user_id = ?
        ''', (entry_id, user_id))
        self.conn.commit()
        self.close()
    
    def get_entry_count(self, user_id):
        self.connect()
        self.cursor.execute('''
            SELECT COUNT(*) FROM diary_entries WHERE user_id = ?
        ''', (user_id,))
        count = self.cursor.fetchone()[0]
        self.close()
        return count


db = DiaryDatabase()
