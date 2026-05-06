import sqlite3
from datetime import datetime

DB_NAME = 'car_hire.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price_per_day INTEGER NOT NULL,
            image_url TEXT,
            is_available BOOLEAN DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            pickup_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            total_price INTEGER NOT NULL,
            status TEXT DEFAULT 'confirmed',
            FOREIGN KEY (car_id) REFERENCES cars (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    cursor.execute("SELECT * FROM admins WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)", 
                      ('admin', 'admin123'))
    
    cursor.execute("SELECT COUNT(*) FROM cars")
    if cursor.fetchone()[0] == 0:
        sample_cars = [
            # Original 5 cars with better, more reliable images
            ('Tesla Model 3', 89, 'https://cdn.pixabay.com/photo/2023/02/02/18/07/tesla-7762962_640.jpg', 1),
            ('BMW i8', 149, 'https://cdn.pixabay.com/photo/2018/03/29/08/08/bmw-3271249_640.jpg', 1),
            ('Mercedes C-Class', 99, 'https://cdn.pixabay.com/photo/2019/06/27/17/13/mercedes-amg-4301607_640.jpg', 1),
            ('Audi A6', 109, 'https://cdn.pixabay.com/photo/2018/03/11/01/04/audi-3215709_640.jpg', 1),
            ('Porsche 911', 299, 'https://cdn.pixabay.com/photo/2014/09/07/22/34/porsche-438199_640.jpg', 1),
            
            # 5 Additional cars (doubling the fleet)
            ('Toyota Camry', 65, 'https://cdn.pixabay.com/photo/2021/01/25/10/48/toyota-5949509_640.jpg', 1),
            ('Honda Civic', 55, 'https://cdn.pixabay.com/photo/2021/01/19/10/54/honda-5931504_640.jpg', 1),
            ('Ford Mustang', 199, 'https://cdn.pixabay.com/photo/2012/11/25/20/04/ford-67138_640.jpg', 1),
            ('Chevrolet Camaro', 179, 'https://cdn.pixabay.com/photo/2015/07/22/23/01/chevrolet-856367_640.jpg', 1),
            ('Lamborghini Huracan', 499, 'https://cdn.pixabay.com/photo/2019/05/30/15/22/lamborghini-4239519_640.jpg', 1),
        ]
        cursor.executemany("INSERT INTO cars (name, price_per_day, image_url, is_available) VALUES (?, ?, ?, ?)", sample_cars)
    
    conn.commit()
    conn.close()

def get_all_cars(filters=None):
    conn = get_db()
    query = "SELECT * FROM cars WHERE is_available = 1"
    params = []
    
    if filters:
        if filters.get('search'):
            query += " AND name LIKE ?"
            params.append(f'%{filters["search"]}%')
        
        if filters.get('min_price') and filters.get('max_price'):
            if filters['min_price'] <= filters['max_price']:
                query += " AND price_per_day BETWEEN ? AND ?"
                params.extend([filters['min_price'], filters['max_price']])
            else:
                # If min > max, swap them
                query += " AND price_per_day BETWEEN ? AND ?"
                params.extend([filters['max_price'], filters['min_price']])
        elif filters.get('min_price'):
            query += " AND price_per_day >= ?"
            params.append(filters['min_price'])
        elif filters.get('max_price'):
            query += " AND price_per_day <= ?"
            params.append(filters['max_price'])
        
        if filters.get('sort') == 'price_asc':
            query += " ORDER BY price_per_day ASC"
        elif filters.get('sort') == 'price_desc':
            query += " ORDER BY price_per_day DESC"
        else:
            query += " ORDER BY id ASC"
    else:
        query += " ORDER BY id ASC"
    
    cars = conn.execute(query, params).fetchall()
    conn.close()
    return cars

def get_car_by_id(car_id):
    conn = get_db()
    car = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
    conn.close()
    return car

def add_car(name, price_per_day, image_url, is_available):
    conn = get_db()
    conn.execute("INSERT INTO cars (name, price_per_day, image_url, is_available) VALUES (?, ?, ?, ?)",
                (name, price_per_day, image_url, is_available))
    conn.commit()
    conn.close()

def update_car(car_id, name, price_per_day, image_url, is_available):
    conn = get_db()
    conn.execute("UPDATE cars SET name = ?, price_per_day = ?, image_url = ?, is_available = ? WHERE id = ?",
                (name, price_per_day, image_url, is_available, car_id))
    conn.commit()
    conn.close()

def delete_car(car_id):
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    future_bookings = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE car_id = ? AND return_date >= ? AND status = 'confirmed'",
        (car_id, today)
    ).fetchone()[0]
    
    if future_bookings == 0:
        conn.execute("DELETE FROM cars WHERE id = ?", (car_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def check_availability(car_id, pickup_date, return_date):
    conn = get_db()
    query = """
        SELECT COUNT(*) FROM bookings 
        WHERE car_id = ? AND status = 'confirmed'
        AND ((pickup_date <= ? AND return_date >= ?) OR
             (pickup_date <= ? AND return_date >= ?) OR
             (pickup_date >= ? AND return_date <= ?))
    """
    params = [car_id, return_date, pickup_date, pickup_date, pickup_date, pickup_date, return_date]
    count = conn.execute(query, params).fetchone()[0]
    conn.close()
    return count == 0

def create_booking(car_id, customer_name, customer_email, pickup_date, return_date, total_price):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO bookings (car_id, customer_name, customer_email, pickup_date, return_date, total_price) VALUES (?, ?, ?, ?, ?, ?)",
        (car_id, customer_name, customer_email, pickup_date, return_date, total_price)
    )
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return booking_id

def get_booking_by_id(booking_id):
    conn = get_db()
    booking = conn.execute("""
        SELECT b.*, c.name as car_name, c.image_url 
        FROM bookings b 
        JOIN cars c ON b.car_id = c.id 
        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    conn.close()
    return booking

def get_all_bookings():
    conn = get_db()
    bookings = conn.execute("""
        SELECT b.*, c.name as car_name 
        FROM bookings b 
        JOIN cars c ON b.car_id = c.id 
        ORDER BY b.pickup_date DESC
    """).fetchall()
    conn.close()
    return bookings

def cancel_booking(booking_id):
    conn = get_db()
    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

def get_all_cars_admin():
    conn = get_db()
    cars = conn.execute("SELECT * FROM cars ORDER BY id ASC").fetchall()
    conn.close()
    return cars
