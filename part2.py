import datetime
from contextlib import AbstractContextManager
from typing import Optional

from sqlalchemy import BigInteger, Float, ForeignKey, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "Books"
    # TODO


class Member(Base):
    __tablename__ = "Members"
    # TODO

    def __init__(self, mid, first_name, last_name, date_of_birth):
        # TODO
        pass

    def borrow_book(self, book: Book) -> None:
        # TODO
        pass

    def return_book(self, book_id) -> float:
        # TODO
        pass


class BorrowingRecord(Base):
    __tablename__ = "BorrowingRecords"
    # TODO

    def __init__(self, book: Book, borrowing_time):
        # TODO
        pass

    def return_book(self) -> float:
        # TODO
        pass


class BaseRepository:
    def __init__(self, session: Session, model_class):
        self.session = session
        self.model_class = model_class

    def get_by_id(self, entity_id):
        return self.session.get(self.model_class, entity_id)

    def get_all(self):
        return list(self.session.scalars(select(self.model_class)))

    def delete(self, entity):
        self.session.delete(entity)

    def add(self, entity):
        self.session.add(entity)


class MemberRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session, Member)

    def get_for_update(self, member_id) -> Optional[Member]:
        """Load the member and lock its row until the transaction ends (supplied code).

        Another transaction that calls get_for_update for the same member waits until this one commits or
        rolls back. SQL Server needs the table hint (SQLAlchemy ignores with_for_update there); other
        databases get SELECT ... FOR UPDATE.
        """
        stmt = (select(Member).where(Member.id == member_id)
                .with_for_update()
                .with_hint(Member, "WITH (UPDLOCK, ROWLOCK)", "mssql"))
        return self.session.scalars(stmt).first()

    def get_borrowed_books(self, member_id) -> list:
        # TODO
        pass


class BookRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session, Book)


class UnitOfWork(AbstractContextManager):
    def __init__(self, SessionFactory):
        self.SessionFactory = SessionFactory
        self.session = None
        self.member_repo = None
        self.book_repo = None

    def __enter__(self):
        # TODO
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        # TODO
        pass


class LibraryService:
    def __init__(self, SessionFactory):
        self.SessionFactory = SessionFactory

    def create_member(self, mid, first_name, last_name, date_of_birth) -> None:
        # TODO
        pass

    def lend_book_to_member(self, member_id, book_id) -> None:
        # TODO
        pass

    def return_book_from_member(self, member_id, book_id) -> float:
        # TODO
        pass

    def get_unreturned_books_for_member(self, member_id) -> list:
        # TODO
        pass


# How to create the Part 2 tables and a session factory for your own tests (run Part 1 first):
# from sqlalchemy import URL, create_engine
# from sqlalchemy.orm import sessionmaker
# url = URL.create("mssql+pyodbc", username="", password="", host="", database="",
#                  query={"driver": "ODBC Driver 18 for SQL Server", "TrustServerCertificate": "yes"})
# engine = create_engine(url)            # add echo=True to print every SQL statement
# Base.metadata.create_all(engine)       # creates Members and BorrowingRecords; Books already exists
# SessionFactory = sessionmaker(bind=engine)
