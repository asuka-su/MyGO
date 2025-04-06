import os
import random
import sqlite3

from datetime import datetime, timedelta

DB_NAME = 'database.db'

class DatabaseManager:
    def __init__(self, db_path='database.db', initial=False):
        self.db_path = db_path
        if initial:
            self._reset_database()
            self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)       

    def _init_db(self):
        print("initializing...")
        with self._get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = 1")
            cursor = conn.cursor()
            cursor.executescript(
                '''
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    username TEXT NOT NULL UNIQUE, 
                    email TEXT NOT NULL UNIQUE
                );
                '''
            )
            conn.commit()
    
    def _reset_database(self):
        print("deleting...")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    ###########################
    ##         user          ##
    ###########################

    def add_user(self, username, email):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    '''INSERT INTO users (username, email) VALUES (?, ?)''', 
                    (username, email)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def delete_user(self, user_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM users WHERE user_id = ?', 
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_users(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT user_id, username, email FROM users'
            )
            return [{
                'user_id': row[0], 
                'username': row[1], 
                'email': row[2], 
            } for row in cursor.fetchall()]
    
    def generate_fake_users(self, count=7):
        users = []
        for i in range(count):
            user_id = str(i)
            users.append({
                'username': f'user_{user_id}', 
                'email': f'user_{user_id}@example.com'
            })
        return users
    
    ###########################
    ##         fake          ##
    ###########################
    def _batch_insert(self, table, data):
        if not data:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                columns = ', '.join(data[0].keys())
                placeholders = ', '.join(['?'] * len(data[0]))
                
                cursor.executemany(
                    f'INSERT INTO {table} ({columns}) VALUES ({placeholders})',
                    [tuple(item.values()) for item in data]
                )
                conn.commit()
            except sqlite3.IntegrityError as e:
                print(f"Somthing is wrong: {str(e)}")
                conn.rollback()
    
    def insert_fake_data(self):
        self._batch_insert('users', self.generate_fake_users())