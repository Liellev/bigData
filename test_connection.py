import pyodbc

# Check installed ODBC drivers
print(pyodbc.drivers())

# Connect to the university database
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=SISE-SQL-Course;"
    "DATABASE=liellevi;"
    "UID=liellevi;"
    "PWD=iHXF3yHDxz;"
    "TrustServerCertificate=YES;"
)

row = conn.execute("SELECT DB_NAME(), SUSER_NAME()").fetchone()
print(row)

conn.close()
