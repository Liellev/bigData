
import os
import pyodbc
from part1 import DatabaseManager

dbm = DatabaseManager(
    "{ODBC Driver 18 for SQL Server}",
    "SISE-SQL-Course",
    "liellevi",
    os.environ["BGU_DB_PASSWORD"],
    "liellevi"
)

# Count books before the test
conn = pyodbc.connect(dbm.connection_string)
try:
    before_count = conn.execute(
        "SELECT COUNT(*) FROM Books"
    ).fetchone()[0]
finally:
    conn.close()

# Test loading invalid CSV
try:
    dbm.file_to_database("test1.csv")
except pyodbc.Error:
    print("Invalid rating correctly rejected!")
else:
    raise AssertionError("TEST FAILED: Invalid data was accepted!")

# Count books after the test
conn = pyodbc.connect(dbm.connection_string)
try:
    after_count = conn.execute(
        "SELECT COUNT(*) FROM Books"
    ).fetchone()[0]
finally:
    conn.close()

assert before_count == after_count, "Rollback failed!"

print("Atomicity test passed!")
