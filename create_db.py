import sqlite3

# Create database connection
conn = sqlite3.connect("database.db")

# Create cursor
cur = conn.cursor()

# Users table
cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    password TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS bookings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    plant_id INTEGER,
    quantity INTEGER
)
""")


cur.execute("""
CREATE TABLE IF NOT EXISTS plantation(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT,
    location TEXT,
    date TEXT,
    plant_count INTEGER
)
""")

# Plants table
cur.execute("""
CREATE TABLE IF NOT EXISTS plants(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_name TEXT,
    description TEXT,
    price REAL,
    image TEXT
)
""")

conn.commit()
conn.close()

print("Tables Created Successfully")