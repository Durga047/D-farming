import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

tables = ["users", "plants", "bookings", "plantation"]

for table in tables:
    print("\n" + "="*40)
    print("TABLE:", table)
    print("="*40)

    cur.execute(f"PRAGMA table_info({table})")

    for col in cur.fetchall():
        print(col)

conn.close()