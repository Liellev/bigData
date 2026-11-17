"""Local tests for Big Data Assignment 1 / Part 2. DO NOT SUBMIT THIS FILE.

Place this file next to your completed part2.py and the supplied check_concurrency.py.
Prerequisite: sql.txt ran, books.csv loaded by part1.py, and Base.metadata.create_all(engine)
has been called (prepare_assignment_local.py does this).
Run: python verify_part2_local.py
The SQL password is read interactively; it is never written to disk.

This is a student-side smoke/regression suite, not the course's hidden grader.
"""
import datetime
import uuid
from getpass import getpass

from sqlalchemy import URL, create_engine, delete, select
from sqlalchemy.orm import sessionmaker

import part2


def expect_value_error(call, description):
    try:
        call()
    except ValueError:
        print(f"PASS: {description} raises ValueError")
    else:
        raise AssertionError(f"Expected ValueError: {description}")


def main():
    username = input("University username (without @post.bgu.ac.il): ").strip()
    if not username:
        raise SystemExit("Username cannot be empty.")
    password = getpass("SQL Server password from SMS: ")
    server = input("SQL server [SISE-SQL-Course]: ").strip() or "SISE-SQL-Course"

    url = URL.create(
        "mssql+pyodbc", username=username, password=password,
        host=server, database=username,
        query={"driver": "ODBC Driver 18 for SQL Server", "TrustServerCertificate": "yes"},
    )
    engine = create_engine(url)
    SessionFactory = sessionmaker(bind=engine)
    created_members = []
    prefix = f"test-{uuid.uuid4().hex[:12]}"

    try:
        with SessionFactory() as session:
            book_ids = list(session.scalars(select(part2.Book.id).order_by(part2.Book.id).limit(7)))
            recent_id = session.scalar(select(part2.Book.id).where(part2.Book.prod_year >= 2020).limit(1))
            older_id = session.scalar(select(part2.Book.id).where(part2.Book.prod_year < 2020).limit(1))
        assert len(book_ids) >= 6, "Load books.csv via part1.py before running tests."
        assert recent_id is not None and older_id is not None, "Need both old and new books from books.csv."
        print("PASS: Part 2 Book mapping can load existing books")

        service = part2.LibraryService(SessionFactory)
        adult_dob = datetime.datetime(1990, 1, 1)
        child_dob = datetime.datetime.now() - datetime.timedelta(days=16 * 365)
        main_id = prefix + "-main"
        created_members.append(main_id)
        service.create_member(main_id, "Test", "Adult", adult_dob)
        with SessionFactory() as session:
            member = session.get(part2.Member, main_id)
            assert member is not None and member.first_name == "Test"
            assert member.borrowing_records == []
        print("PASS: create_member saves a member and an empty borrowing list")

        assert service.get_unreturned_books_for_member(main_id) == []
        service.lend_book_to_member(main_id, book_ids[0])
        with SessionFactory() as session:
            records = list(session.scalars(select(part2.BorrowingRecord).where(
                part2.BorrowingRecord.member_id == main_id
            )))
            assert len(records) == 1, f"One loan should create exactly one row; found {len(records)}."
            assert records[0].book_id == book_ids[0]
            assert records[0].return_time is None
            assert (datetime.datetime.now() - records[0].borrowing_time) < datetime.timedelta(minutes=2)
            repo = part2.MemberRepository(session)
            assert repo.get_borrowed_books(main_id) == [book_ids[0]]
            assert repo.get_borrowed_books("missing-" + prefix) == []
            expected_title = session.get(part2.Book, book_ids[0]).title
        assert service.get_unreturned_books_for_member(main_id) == [expected_title]
        print("PASS: loan saved once; repositories return IDs; service returns titles")

        expect_value_error(
            lambda: service.lend_book_to_member(main_id, book_ids[0]),
            "the same member borrowing an unreturned book twice",
        )
        for bid in book_ids[1:5]:
            service.lend_book_to_member(main_id, bid)
        assert len(service.get_unreturned_books_for_member(main_id)) == 5
        expect_value_error(
            lambda: service.lend_book_to_member(main_id, book_ids[5]),
            "a sixth concurrent outstanding book",
        )
        assert len(service.get_unreturned_books_for_member(main_id)) == 5
        print("PASS: five loans allowed; sixth refused without changing database")

        missing_book_id = 999999999999999
        with SessionFactory() as session:
            assert session.get(part2.Book, missing_book_id) is None
        expect_value_error(
            lambda: service.lend_book_to_member(main_id, missing_book_id),
            "borrowing a nonexistent book",
        )
        expect_value_error(
            lambda: service.return_book_from_member(main_id, book_ids[5]),
            "returning a book never borrowed by this member",
        )
        assert len(service.get_unreturned_books_for_member(main_id)) == 5

        fine = service.return_book_from_member(main_id, book_ids[0])
        assert isinstance(fine, float) and fine == 0.0, f"On-time fine should be 0.0; got {fine!r}."
        assert len(service.get_unreturned_books_for_member(main_id)) == 4
        expect_value_error(
            lambda: service.return_book_from_member(main_id, book_ids[0]),
            "returning the same loan twice",
        )
        service.lend_book_to_member(main_id, book_ids[0])
        with SessionFactory() as session:
            same_book_records = list(session.scalars(select(part2.BorrowingRecord).where(
                part2.BorrowingRecord.member_id == main_id,
                part2.BorrowingRecord.book_id == book_ids[0],
            )))
            assert len(same_book_records) == 2
            assert sum(r.return_time is None for r in same_book_records) == 1
        print("PASS: on-time return has zero fine, double return refused, reborrowing allowed")

        # Fines: set borrowing_time in the database, as the assignment suggests.
        fine_cases = [
            ("child_recent", child_dob, recent_id, 34, 2, 50.0),
            ("adult_old", adult_dob, older_id, 31, 1, 20.0),
            ("adult_on_time", adult_dob, recent_id, 10, 0, 0.0),
        ]
        for case, dob, bid, days, hours, expected in fine_cases:
            member_id = prefix + "-" + case
            created_members.append(member_id)
            service.create_member(member_id, "Test", case, dob)
            service.lend_book_to_member(member_id, bid)
            with SessionFactory.begin() as session:
                rec = session.scalars(select(part2.BorrowingRecord).where(
                    part2.BorrowingRecord.member_id == member_id,
                    part2.BorrowingRecord.book_id == bid,
                    part2.BorrowingRecord.return_time.is_(None),
                )).one()
                rec.borrowing_time = datetime.datetime.now() - datetime.timedelta(days=days, hours=hours)
            actual = service.return_book_from_member(member_id, bid)
            assert isinstance(actual, float) and abs(actual - expected) < 1e-8, (
                f"{case}: expected {expected} NIS, got {actual!r}"
            )
            with SessionFactory() as session:
                rec = session.scalars(select(part2.BorrowingRecord).where(
                    part2.BorrowingRecord.member_id == member_id
                )).one()
                assert rec.return_time is not None
            print(f"PASS: {case} fine = {actual} NIS and return_time persisted")

        rollback_id = prefix + "-rollback"
        created_members.append(rollback_id)
        try:
            with part2.UnitOfWork(SessionFactory) as uow:
                assert uow.member_repo.session is uow.book_repo.session
                uow.member_repo.add(part2.Member(rollback_id, "Roll", "Back", adult_dob))
                raise ValueError("Intentional rollback test")
        except ValueError as exc:
            assert str(exc) == "Intentional rollback test"
        with SessionFactory() as session:
            assert session.get(part2.Member, rollback_id) is None
        print("PASS: UnitOfWork shares a session, rolls back and propagates exceptions")

        # Uses the course-provided script's function; no need to put credentials inside it.
        try:
            import check_concurrency
        except ImportError as exc:
            raise AssertionError("Put the provided check_concurrency.py next to this file.") from exc
        assert check_concurrency.check(SessionFactory), "Concurrency check failed: limit broken or unexpected error."
        print("PASS: provided concurrency check (two simultaneous librarians)")
        print("\nALL LOCAL PART 2 CHECKS PASSED. This is NOT the hidden autograder.")

    finally:
        # Delete ONLY the temporary members created by this test, not the books or other students' data.
        if created_members:
            with SessionFactory.begin() as session:
                session.execute(delete(part2.BorrowingRecord).where(
                    part2.BorrowingRecord.member_id.in_(created_members)
                ))
                session.execute(delete(part2.Member).where(part2.Member.id.in_(created_members)))
        engine.dispose()
        print("Temporary test-* members cleaned up. The provided concurrency check may leave race-* test members.")


if __name__ == "__main__":
    main()
