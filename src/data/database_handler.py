import sqlite3
from datetime import datetime, timedelta
from utils.file_handler import FileHandler
import json

class DatabaseHandler:
    def __init__(self, db_path="backup_tasks.db"):
        self.db_path = FileHandler.get_paht(db_path)
        self.init_database()

    def init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS BackupTask (
                    id INTEGER PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    encrypt BOOLEAN NOT NULL,
                    frequency TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    backup_limit INTEGER NOT NULL,
                    agent_id TEXT NOT NULL,
                    start_date TIMESTAMP NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    is_directory BOOLEAN NOT NULL,
                    last_run TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS BackupHistory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    backup_id TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES BackupTask(id)
                )
            ''')
            conn.commit()