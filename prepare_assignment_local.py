"""Local preparation for Big Data Assignment 1. DO NOT SUBMIT THIS FILE.

Prerequisite: use SSMS to run sql.txt on a freshly cleared course database.
Run: python prepare_assignment_local.py
The university password is prompted securely, not stored in this file.
"""
from contextlib import closing
from getpass import getpass
from pathlib import Path

import pyodbc
from sqlalchemy import URL, create_engine, func, select
from sqlalchemy.orm import sessionmaker

from part1 import DatabaseManager
from part2 import Base, Book


def main():
    here = Path(__file__).resolve().parent
    csv_path = here / "books.csv"
    if not csv_path.is_file():
        raise SystemExit("Missing books.csv: put this helper in the same directory as books.csv, part1.py, part2.py.")

    username = input("University username (without @post.bgu.ac.il): ").strip()
    if not username:
        raise SystemExit("Username cannot be empty.")
    password = getpass("SQL Server password from SMS: ")
    server = input("SQL server [SISE-SQL-Course]: ").strip() or "SISE-SQL-Course"

    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server};DATABASE={username};UID={username};"
        f"PWD={password};TrustServerCertificate=YES;"
    )
    with closing(pyodbc.connect(connection_string)) as connection:
        actual_db, actual_login = connection.cursor().execute(
            "SELECT DB_NAME(), SUSER_NAME()"
        ).fetchone()
        current_count = connection.cursor().execute(
            "SELECT COUNT(*) FROM dbo.Books"
        ).fetchone()[0]
    print(f"Connected: database={actual_db}, login={actual_login}.")
    if str(actual_db).lower() != username.lower():
        raise SystemExit("Wrong database; do not continue.")
    if current_count != 0:
        raise SystemExit(
            f"Books already has {current_count} rows. Do NOT load again. "
            "Either continue directly to verify_part2_local.py, or reset in SSMS using the course guide."
        )

    dbm = DatabaseManager(
        "{ODBC Driver 18 for SQL Server}", server, username, password, username
    )
    dbm.file_to_database(str(csv_path))
    dbm.add_summary_items()
    print("Part 1 loaded:")
    print("  best book in 2025:", dbm.get_best_books().get(2025))
    print("  two best years:", dbm.get_n_best_years(2))

    url = URL.create(
        "mssql+pyodbc", username=username, password=password,
        host=server, database=username,
        query={"driver": "ODBC Driver 18 for SQL Server", "TrustServerCertificate": "yes"},
    )
    engine = create_engine(url)
    try:
        Base.metadata.create_all(engine)
        SessionFactory = sessionmaker(bind=engine)
        with SessionFactory() as session:
            book_count = session.scalar(select(func.count()).select_from(Book))
            print(f"Part 2 tables created / confirmed. Books count from ORM: {book_count}")
        if book_count != 26:
            raise AssertionError(f"Expected 26 books from supplied books.csv; found {book_count}.")
        assert dbm.get_best_books()[2025] == "Big Data Bigger Problems"
        assert dbm.get_n_best_years(2) == [2025, 1999]
        print("PASS: basic Part 1 and Part 2 preparation checks.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
