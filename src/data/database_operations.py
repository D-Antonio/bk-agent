import sqlite3
from datetime import datetime
from data.database_handler import DatabaseHandler

class DatabaseOperations:
    def __init__(self, db_path="backup_tasks.db"):
        self.db_handler = DatabaseHandler(db_path)

    def add_backup_task(self, parameters):
        with sqlite3.connect(self.db_handler.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           INSERT INTO BackupTask (
                           id, source_path, encrypt, frequency, provider, 
                           backup_limit, agent_id, start_date, is_active, is_directory, last_run
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                           (parameters['id'],
                            parameters['source_path'],
                            parameters['encrypt'],
                            parameters['frequency'],
                            parameters['provider'],
                            parameters['backup_limit'],
                            parameters['agent_id'],
                            parameters['start_date'],
                            parameters['is_active'],
                            parameters['is_directory'],
                            parameters['last_run']
                            ))
            conn.commit()

    def fetch_daily_tasks(self, current_date):
        with sqlite3.connect(self.db_handler.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT * FROM BackupTask 
                           WHERE is_active = 1 
                           AND date(start_date) <= date(?)''', 
                           (current_date, ))
            
            return cursor.fetchall()
        
    def get_backup_history(self, task_id):
        with sqlite3.connect(self.db_handler.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT backup_id FROM BackupHistory 
                           WHERE task_id = ? 
                           ORDER BY timestamp ASC
                           ''', (task_id,))
            
            return cursor.fetchall()

    def update_backup_task(self, task_id, current_date_str, next_run_str):
        with sqlite3.connect(self.db_handler.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           UPDATE BackupTask 
                           SET last_run = ?, start_date = ?
                           WHERE id = ?''', (current_date_str, next_run_str, task_id))
            
            conn.commit()

    def record_backup_history(self, task_id, backup_id, original_name, current_date_str):
        with sqlite3.connect(self.db_handler.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           INSERT INTO BackupHistory (
                           task_id, backup_id, original_name, timestamp, status
                           ) VALUES (?, ?, ?, ?, ?)''', (task_id,backup_id,original_name,current_date_str,'completed'))
            
            conn.commit()

    def delete_backup(self, backup_id):
        with sqlite3.connect(self.db_handler.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM BackupHistory WHERE backup_id = ?', (backup_id,))

            conn.commit()

    def delete_task(self, task_id):
        with sqlite3.connect(self.db_handler.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM BackupTask WHERE id = ?', (task_id,))
            cursor.execute('DELETE FROM BackupHistory WHERE task_id = ?', (task_id,))

            conn.commit()

    def get_backup_info(self, backup_id):
        with sqlite3.connect(self.db_handler.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT T.source_path, T.is_directory, T.provider, T.encrypt, H.timestamp, H.original_name, H.task_id, H.backup_id
                           FROM BackupTask AS T
                            JOIN BackupHistory AS H ON T.id = H.task_id
                            WHERE H.backup_id = ?
                            ORDER BY H.timestamp DESC
                            LIMIT 1''', (backup_id,))
            
            return cursor.fetchone() 