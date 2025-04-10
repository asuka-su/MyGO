import os
import random
import sqlite3

from datetime import datetime, timedelta, date
import time

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

            # 地点表
            cursor.execute('''
                CREATE TABLE locations (
                    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    address TEXT,
                    type TEXT CHECK(type IN ('attraction','restaurant','transport'))
                )''')
            
            cursor.execute('''
                CREATE TABLE trip_locations (
                    location_id INTEGER NOT NULL REFERENCES locations(location_id) ON DELETE CASCADE,
                    trip_id INTEGER NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE, 
                    PRIMARY KEY (location_id, trip_id)
                )''')

            # 足迹表
            cursor.execute('''
                CREATE TABLE footprints (
                    footprint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT,
                    image_url TEXT,
                    created_at DATETIME NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    location_id INTEGER NOT NULL REFERENCES locations(location_id)
                )''')
            
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
    
    ###########################
    ##         trip          ##
    ###########################

    def create_trip(self, participants, start_day, end_day, location_ids):
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

                if location_ids:
                    unique_locations = list(set(location_ids))
                    placeholders = ', '.join(['?'] * len(unique_locations))
                    cursor.execute(f'''
                        SELECT location_id FROM locations
                        WHERE location_id IN ({placeholders})
                    ''', unique_locations)
                    valid_locations = [row[0] for row in cursor.fetchall()]

                    if valid_locations:
                        cursor.executemany('''
                            INSERT INTO trip_locations VALUES (?, ?)
                        ''', [(lid, trip_id) for lid in valid_locations])

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
                SELECT 
                    t.trip_id, 
                    t.start_day, 
                    t.end_day,
                    (
                        SELECT GROUP_CONCAT(u.username, ', ') 
                        FROM trip_participants tp
                        INNER JOIN users u ON tp.user_id = u.user_id
                        WHERE tp.trip_id = t.trip_id
                    ),
                    (
                        SELECT GROUP_CONCAT(l.name, ', ') 
                        FROM trip_locations tl
                        INNER JOIN locations l ON tl.location_id = l.location_id
                        WHERE tl.trip_id = t.trip_id
                    )
                FROM trips t
                ORDER BY t.start_day DESC
            ''')
            return [{
                'trip_id': row[0],
                'start_day': row[1],
                'end_day': row[2],
                'participants': row[3], 
                'locations': row[4] if row[4] is not None else '', 
            } for row in cursor.fetchall()]
    
    def get_trips_by_filters(self, participants, 
                             start_after=None, start_before=None, 
                             end_after=None, end_before=None, arrived_locations=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
        
            participant_query = '''
                SELECT t.trip_id
                FROM trips t
                JOIN trip_participants tp ON t.trip_id = tp.trip_id
                WHERE tp.user_id IN ({})
                GROUP BY t.trip_id
                HAVING COUNT(DISTINCT tp.user_id) = ?
            '''.format(','.join(['?']*len(participants)))
        
            cursor.execute(participant_query, participants + [len(participants)])
            candidate_ids = [str(row[0]) for row in cursor.fetchall()]

            if arrived_locations:
                location_query = '''
                    SELECT t.trip_id
                    FROM trips t
                    JOIN trip_locations tl ON t.trip_id = tl.trip_id
                    WHERE tl.location_id IN ({})
                    GROUP BY t.trip_id
                    HAVING COUNT(DISTINCT tl.location_id) = ?
                '''.format(','.join(['?']*len(arrived_locations)))
                cursor.execute(location_query, arrived_locations + [len(arrived_locations)])
                candidate_ids_2 = [str(row[0]) for row in cursor.fetchall()]
                candidate_ids = list(set(candidate_ids) & set(candidate_ids_2))

            if not candidate_ids:
                return []

            time_query = '''
                SELECT t.trip_id, t.start_day, t.end_day
                FROM trips t
                WHERE t.trip_id IN ({})
            '''.format(','.join(['?']*len(candidate_ids)))
        
            time_conditions = []
            time_params = []
            if start_after:
                time_conditions.append("t.start_day >= ?")
                time_params.append(start_after)
            if start_before:
                time_conditions.append("t.start_day <= ?")
                time_params.append(start_before)
            if end_after:
                time_conditions.append("t.end_day >= ?")
                time_params.append(end_after)
            if end_before:
                time_conditions.append("t.end_day <= ?")
                time_params.append(end_before)
        
            if time_conditions:
                time_query += " AND " + " AND ".join(time_conditions)
        
            cursor.execute(time_query, candidate_ids + time_params)
            trip_data = cursor.fetchall()

            if not trip_data:
                return []

            trip_ids = [str(t[0]) for t in trip_data]
            participant_query = f'''
                SELECT tp.trip_id, u.user_id, u.username
                FROM trip_participants tp
                JOIN users u ON tp.user_id = u.user_id
                WHERE tp.trip_id IN ({','.join(trip_ids)})
            '''
            cursor.execute(participant_query)
            participant_map = {}
            for row in cursor.fetchall():
                trip_id = row[0]
                if trip_id not in participant_map:
                    participant_map[trip_id] = []
                participant_map[trip_id].append({
                    'user_id': row[1],
                    'username': row[2]
                })
            
            location_query = f'''
                SELECT tl.trip_id, l.location_id, l.name
                FROM trip_locations tl
                JOIN locations l ON tl.location_id = l.location_id
                WHERE tl.trip_id IN ({','.join(trip_ids)})
            '''
            cursor.execute(location_query)
            location_map = {}
            for row in cursor.fetchall():
                trip_id = row[0]
                if trip_id not in location_map:
                    location_map[trip_id] = []
                location_map[trip_id].append({
                    'location_id': row[1],
                    'locationname': row[2]
                })
            
            return [{
                'trip_id': t[0],
                'start_day': datetime.strptime(t[1], "%Y-%m-%d").date(),
                'end_day': datetime.strptime(t[2], "%Y-%m-%d").date(),
                'participants': participant_map.get(t[0], []), 
                'locations': location_map.get(t[0], []), 
            } for t in trip_data]
        

    ###########################
    ##       footprint       ##
    ###########################

    def create_footprint(self, user_id, title, content, location_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO footprints 
                    (title, content, image_url, created_at, user_id, location_id)
                    VALUES (?, ?, ?, datetime('now'), ?, ?)
                ''', (title, content, f'img_{int(time.time())}.jpg', user_id, location_id))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                print(f"创建足迹失败: {str(e)}")
                return None

    def get_all_footprints(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    f.footprint_id, 
                    f.title, 
                    f.content, 
                    f.image_url, 
                    f.created_at,
                    f.user_id,
                    l.location_id,
                    l.name as location_name,
                    l.type as location_type,
                    u.username
                FROM footprints f
                JOIN users u ON f.user_id = u.user_id
                JOIN locations l ON f.location_id = l.location_id
                ORDER BY f.created_at DESC
            ''')
            footprints = []
            for row in cursor.fetchall():
                # 格式化时间
                created_at = datetime.strptime(row[4], '%Y-%m-%d %H:%M:%S') if isinstance(row[4], str) else row[4]
                formatted_time = created_at.strftime('%Y-%m-%d %H:%M')
                
                footprints.append({
                    'footprint_id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'image_url': row[3],
                    'created_at': formatted_time,
                    'user_id': row[5],
                    'location_id': row[6],
                    'location_name': row[7],
                    'location_type': row[8],
                    'username': row[9]
                })
            return footprints
        
    def get_footprints_by_filters(self, username=None, location_name=None, 
                            location_types=None, created_after=None, 
                            created_before=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT 
                    f.footprint_id, 
                    f.title, 
                    f.content, 
                    f.image_url, 
                    f.created_at,
                    f.user_id,
                    l.location_id,
                    l.name as location_name,
                    l.type as location_type,
                    u.username
                FROM footprints f
                JOIN users u ON f.user_id = u.user_id
                JOIN locations l ON f.location_id = l.location_id
                WHERE 1=1
            '''
            params = []
            
            # 用户名筛选
            if username:
                query += " AND u.username LIKE ?"
                params.append(f"%{username}%")
            
            # 地点名称筛选
            if location_name:
                query += " AND l.name LIKE ?"
                params.append(f"%{location_name}%")
            
            # 地点类型筛选
            if location_types:
                placeholders = ','.join(['?']*len(location_types))
                query += f" AND l.type IN ({placeholders})"
                params.extend(location_types)
            
            # 时间范围筛选
            if created_after:
                query += " AND datetime(f.created_at) >= datetime(?)"
                params.append(created_after)
            if created_before:
                query += " AND datetime(f.created_at) <= datetime(?)"
                params.append(created_before)
            
            query += " ORDER BY f.created_at DESC"
            
            cursor.execute(query, params)
            
            footprints = []
            for row in cursor.fetchall():
                created_at = datetime.strptime(row[4], '%Y-%m-%d %H:%M:%S') if isinstance(row[4], str) else row[4]
                footprints.append({
                    'footprint_id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'image_url': row[3],
                    'created_at': created_at.strftime('%Y-%m-%d %H:%M'),
                    'user_id': row[5],
                    'location_id': row[6],
                    'location_name': row[7],
                    'location_type': row[8],
                    'username': row[9]
                })
            return footprints
    
    ###########################
    ##       location        ##
    ###########################
    
    def create_location(self, name, address, location_type):
        """
        创建新地点并验证城市有效性
        参数:
            name: 地点名称 (必填)
            address: 地址信息
            location_type: 类型必须为 attraction/restaurant/transport
        返回: 新创建地点的location_id
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 验证类型有效性
                valid_types = {'attraction', 'restaurant', 'transport'}
                if location_type not in valid_types:
                    raise ValueError(f"Invalid type: {location_type}. Must be one of {valid_types}")

                # 插入主记录
                cursor.execute('''
                    INSERT INTO locations 
                    (name, address, type)
                    VALUES (?, ?, ?)
                ''', (name, address, location_type))
                
                location_id = cursor.lastrowid
                conn.commit()
                return location_id

            except sqlite3.IntegrityError as e:
                conn.rollback()
                if "UNIQUE constraint" in str(e):
                    raise Exception(f"Location name '{name}' already exists")
                raise Exception(f"Database integrity error: {str(e)}")
                
            except sqlite3.Error as e:
                conn.rollback()
                raise Exception(f"Database operation failed: {str(e)}")
                
            except ValueError as ve:
                conn.rollback()
                raise ve 
    

    def get_all_locations(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT l.location_id, l.name
                FROM locations l
            ''')
            return [{
                'location_id': row[0],
                'name': row[1],
            } for row in cursor.fetchall()]

    ###########################
    ##         fake          ##
    ###########################
    
    def insert_fake_data(self):
        available_user_ids = []
        for i in range(15):
            self.create_user(f"User_{i}", f"{i}_{i}@example.com")
            available_user_ids.append(i+1)

        locations = [
            {'name': 'Eiffel Tower', 'address': 'Paris', 'type': 'attraction'},
            {'name': 'Louvre Museum', 'address': 'Paris', 'type': 'attraction'},
            {'name': 'Big Ben', 'address': 'London', 'type': 'attraction'},
            {'name': 'Daxing Airport', 'address': 'Beijing', 'type': 'transport'},
            {'name': 'Beijing West Railway Station', 'address': 'Beijing', 'type': 'transport'},
            {'name': 'Peking Duck Restaurant', 'address': 'Beijing', 'type': 'restaurant'},
            {'name': 'Sushi Place', 'address': 'Tokyo', 'type': 'restaurant'},
            {'name': 'Great Wall', 'address': 'Beijing', 'type': 'attraction'},
            {'name': 'Forbidden City', 'address': 'Beijing', 'type': 'attraction'},
            {'name': 'Tokyo Tower', 'address': 'Tokyo', 'type': 'attraction'}
        ]

        available_location_ids = []
        for i, location in enumerate(locations):
            self.create_location(location['name'], location['address'], location['type'])
            available_location_ids.append(i + 1)

        for _ in range(10):
            start_date = date.today() + timedelta(days=random.randint(1, 30))
            end_date = start_date + timedelta(days=random.randint(1, 14))
            num_participants = random.randint(1, 4)
            selected_users = random.sample(available_user_ids, num_participants)
            num_locations = random.randint(0, 2)
            selected_locations = random.sample(available_location_ids, num_locations)
            self.create_trip(selected_users, start_date, end_date, selected_locations)
        