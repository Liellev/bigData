import pyodbc


class DatabaseManager:
    def __init__(self, driver: str, server: str, username: str, password: str, database: str):
         self.connection_string = (
            f"DRIVER={driver};SERVER={server};DATABASE={database};"
            f"UID={username};PWD={password};TrustServerCertificate=YES;"
        )


    def file_to_database(self, path: str) -> None:

        conn = pyodbc.connect(self.connection_string)

        try:
            cursor = conn.cursor()

            with open(path, "r", encoding="utf-8") as file:
                for line in file:
                    title, author, year, rating = line.strip().split(",")

                    cursor.execute(
                        """
                        INSERT INTO Books
                            (title, author_name, prod_year, rating)
                        VALUES (?, ?, ?, ?)
                        """,
                        title, author, int(year), float(rating)
                    )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()


    def add_summary_items(self) -> None:
        conn = pyodbc.connect(self.connection_string)

        try:
            cursor = conn.cursor()
            cursor.execute("EXEC AddSummaryItems")
            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def get_best_books(self) -> dict[int, str]:
       
        conn = pyodbc.connect(self.connection_string)

        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT a.prod_year, b.title
                FROM AnnualSummary AS a
                JOIN Books AS b
                    ON a.book_id = b.id
            """)

            rows = cursor.fetchall()

            result = {}
            for row in rows:
                result[row.prod_year] = row.title

            return result

        finally:
            conn.close()


    def get_n_best_years(self, n: int) -> list[int]:
        conn = pyodbc.connect(self.connection_string)

        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT TOP (?) prod_year
                FROM AnnualSummary
                ORDER BY rated_above_8 DESC, prod_year ASC;
            """, n)

            rows = cursor.fetchall()
            return [row.prod_year for row in rows]

        finally:
            conn.close()

    
    def update_rating(self, book_id: int, rating: float) -> None:
        conn = pyodbc.connect(self.connection_string)

        try:
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE Books SET rating = ? WHERE id = ?",
                rating,
                book_id
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

