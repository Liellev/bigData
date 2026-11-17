import datetime
from contextlib import AbstractContextManager
from typing import Optional
import math

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "Books"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_name: Mapped[str] = mapped_column(String(200))
    prod_year: Mapped[int] = mapped_column(BigInteger)
    rating: Mapped[float] = mapped_column(Float)


class Member(Base):
    __tablename__ = "Members"
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    date_of_birth: Mapped[datetime.datetime] = mapped_column(DateTime)
    borrowing_records: Mapped[list["BorrowingRecord"]] = relationship(back_populates="member")

    def __init__(self, mid, first_name, last_name, date_of_birth):
        self.id = mid
        self.first_name = first_name
        self.last_name = last_name
        self.date_of_birth = date_of_birth
        self.borrowing_records = []

    def borrow_book(self, book: Book) -> None:
        active_records = [ record for record in self.borrowing_records
            if record.return_time is None]

        for record in active_records:
            existing_id = (record.book_id if record.book_id is not None
                           else record.book.id)
            if existing_id == book.id:
                raise ValueError("Member already has this book!")

        if len(active_records) >= 5:
            raise ValueError("Member already has five unreturned books!")

        self.borrowing_records.append(
            BorrowingRecord(book, datetime.datetime.now())
        )

    def return_book(self, book_id) -> float:
        for record in self.borrowing_records:
            if record.return_time is None:
                existing_id = (record.book_id if record.book_id is not None
                               else record.book.id)
                if existing_id == book_id:
                    return record.return_book()
        raise ValueError("No active loan for this book")


class BorrowingRecord(Base):
    __tablename__ = "BorrowingRecords"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("Members.id"), index=True
    )
    member: Mapped["Member"] = relationship(back_populates="borrowing_records")
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("Books.id"))
    book: Mapped["Book"] = relationship()
    borrowing_time: Mapped[datetime.datetime] = mapped_column(DateTime)
    return_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True)

    def __init__(self, book: Book, borrowing_time):
        self.book = book
        self.borrowing_time = borrowing_time
        self.return_time = None

    def return_book(self) -> float:
        self.return_time = datetime.datetime.now()
        elapsed = self.return_time - self.borrowing_time
        borrowed_days = math.ceil(elapsed.total_seconds() / (24 * 60 * 60))
        late_days = max(0, borrowed_days - 30)

        daily_cost = 20.0 if self.book.prod_year >= 2020 else 10.0
        fine = late_days * daily_cost

        dob = self.member.date_of_birth.date()
        returned_on = self.return_time.date()
        age = (returned_on.year - dob.year
               - ((returned_on.month, returned_on.day) < (dob.month, dob.day)))
        if age < 18:
            fine *= 0.5

        return float(fine)


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
        stmt = select(BorrowingRecord.book_id).where(
            BorrowingRecord.member_id == member_id,
            BorrowingRecord.return_time.is_(None)
        )
        return list(self.session.scalars(stmt))


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
        self.session = self.SessionFactory()
        self.member_repo = MemberRepository(self.session)
        self.book_repo = BookRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                try:
                    self.session.commit()
                except Exception:
                    self.session.rollback()
                    raise
            else:
                self.session.rollback()
        finally:
            self.session.close()
        return False


class LibraryService:
    def __init__(self, SessionFactory):
        self.SessionFactory = SessionFactory

    def create_member(self, mid, first_name, last_name, date_of_birth) -> None:
        with UnitOfWork(self.SessionFactory) as uow:
            member = Member(mid, first_name, last_name, date_of_birth)
            uow.member_repo.add(member)

    def lend_book_to_member(self, member_id, book_id) -> None:
        with UnitOfWork(self.SessionFactory) as uow:
            member = uow.member_repo.get_for_update(member_id)
            book = uow.book_repo.get_by_id(book_id)
            if book is None:
                raise ValueError("Book doesnt exist")
            member.borrow_book(book)

    def return_book_from_member(self, member_id, book_id) -> float:
        with UnitOfWork(self.SessionFactory) as uow:
            member = uow.member_repo.get_for_update(member_id)
            return member.return_book(book_id)

    def get_unreturned_books_for_member(self, member_id) -> list:
        with UnitOfWork(self.SessionFactory) as uow:
            member = uow.member_repo.get_by_id(member_id)
            return [
                record.book.title
                for record in member.borrowing_records
                if record.return_time is None
            ]


# How to create the Part 2 tables and a session factory for your own tests (run Part 1 first):
# from sqlalchemy import URL, create_engine
# from sqlalchemy.orm import sessionmaker
# url = URL.create("mssql+pyodbc", username="", password="", host="", database="",
#                  query={"driver": "ODBC Driver 18 for SQL Server", "TrustServerCertificate": "yes"})
# engine = create_engine(url)            # add echo=True to print every SQL statement
# Base.metadata.create_all(engine)       # creates Members and BorrowingRecords; Books already exists
# SessionFactory = sessionmaker(bind=engine)
