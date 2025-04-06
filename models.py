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
            
            cursor.execute('''
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE
                )''')
            
            cursor.execute('''
                CREATE TABLE trips (
                    trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_day DATE NOT NULL,
                    end_day DATE NOT NULL CHECK(end_day > start_day)
                )''')
            
            cursor.execute('''
                CREATE TABLE trip_participants (
                    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    trip_id INTEGER NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE, 
                    PRIMARY KEY (user_id, trip_id)
                )''')
            
            cursor.execute('''
                CREATE TRIGGER clean_empty_trips
                AFTER DELETE ON trip_participants
                FOR EACH ROW
                BEGIN
                    DELETE FROM trips
                    WHERE trip_id = OLD.trip_id
                    AND (SELECT COUNT(*) FROM trip_participants WHERE trip_id = OLD.trip_id) = 0;
                END
            ''')
            
            conn.commit()
    
    def _reset_database(self):
        print("deleting...")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    ###########################
    ##         user          ##
    ###########################

    def create_user(self, username, email):
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
            cursor.execute('DELETE FROM trip_participants WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
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
    ##         trip          ##
    ###########################
    def create_trip(self, participants, start_day, end_day):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    '''INSERT INTO trips (start_day, end_day) VALUES (?, ?)''', 
                    (start_day, end_day)
                )
                trip_id = cursor.lastrowid

                unique_participants = list(set(participants))
                placeholders = ', '.join(['?'] * len(unique_participants))
                cursor.execute(f'''
                    SELECT user_id FROM users
                    WHERE user_id IN ({placeholders})
                ''', unique_participants)
                valid_users = [row[0] for row in cursor.fetchall()]

                if len(valid_users) == 0:
                    raise ValueError('Unable to create trip: No valid participants!')
                
                cursor.executemany('''
                    INSERT INTO trip_participants VALUES (?, ?)
                ''', [(user_id, trip_id) for user_id in valid_users])

                conn.commit()
                return trip_id
            except sqlite3.Error as e:
                conn.rollback()
                raise Exception(f"Unable to create trip: {str(e)}")
    
    def delete_trip(self, trip_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM trips WHERE trip_id = ?', (trip_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_trips(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.trip_id, t.start_day, t.end_day, 
                    GROUP_CONCAT(u.username, ', ') 
                FROM trips t
                LEFT JOIN trip_participants tp ON t.trip_id = tp.trip_id
                LEFT JOIN users u ON tp.user_id = u.user_id
                GROUP BY t.trip_id
                ORDER BY t.start_day DESC
            ''')
            return [{
                'trip_id': row[0],
                'start_day': row[1],
                'end_day': row[2],
                'participants': row[3]
            } for row in cursor.fetchall()]
    
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

