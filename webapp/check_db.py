import sqlite3


connection = sqlite3.connect("app.db")

cursor = connection.cursor()

cursor.execute(
    """
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    ORDER BY name
    """
)

tables = cursor.fetchall()

for table in tables:
    print(table[0])

connection.close()