"""Does your code keep the 5-book limit when two librarians lend to the same member at the same moment?

Run it from the folder of your part2.py, after Part 1 has loaded the books:

    python check_concurrency.py

Fill in your connection details below first. Each run creates a new member, so you can run it as often as you
like. Do not submit this file.

How it works: two threads lend a book to the same member at the same time. Inside borrow_book, a short pause
between "read the member's loans" and "apply the rule" lets both requests read before either one commits. Real
requests that arrive together do the same, only rarely and by chance, which is why such bugs pass every test.
"""
import datetime
import logging
import threading

from sqlalchemy import URL, create_engine, func, select
from sqlalchemy.orm import sessionmaker

import part2

DATABASE_URL = URL.create("mssql+pyodbc", username="", password="", host="", database="",
                          query={"driver": "ODBC Driver 18 for SQL Server", "TrustServerCertificate": "yes"})
PAUSE_SECONDS = 3   # how long a request waits for the other one between reading the loans and applying the rule
log = logging.getLogger("check_concurrency")


def two_loans_at_once(service, member_id, book_a, book_b) -> dict:
    """Lend book_a and book_b to member_id in two threads at once; return what happened to each loan."""
    barrier = threading.Barrier(2, timeout=PAUSE_SECONDS)
    original = part2.Member.borrow_book

    def paused_borrow_book(self, book):
        len(self.borrowing_records)        # read the member's loans: what the rule looks at
        try:
            barrier.wait()                 # wait for the other request to read too (gives up after the timeout)
        except threading.BrokenBarrierError:
            pass
        return original(self, book)

    outcomes = {}

    def lend(book_id):
        try:
            service.lend_book_to_member(member_id, book_id)
            outcomes[book_id] = "lent"
        except ValueError as e:
            outcomes[book_id] = f"refused: {e}"
        except Exception as e:             # any other error is a bug in the code under test: report it
            outcomes[book_id] = f"ERROR {type(e).__name__}: {e}"

    part2.Member.borrow_book = paused_borrow_book
    try:
        threads = [threading.Thread(target=lend, args=(b,)) for b in (book_a, book_b)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        part2.Member.borrow_book = original
    return outcomes


def check(session_factory) -> bool:
    """Run the check against the database behind session_factory; True if the limit held."""
    service = part2.LibraryService(session_factory)
    with session_factory() as session:
        book_ids = list(session.scalars(select(part2.Book.id).order_by(part2.Book.id).limit(6)))
        earlier_runs = session.scalar(select(func.count()).select_from(part2.Member)
                                      .where(part2.Member.id.like("race-%")))
    if len(book_ids) < 6:
        raise SystemExit("Load the books first (Part 1: file_to_database).")

    member_id = f"race-{earlier_runs + 1}"         # a new member on every run, numbered in order
    service.create_member(member_id, "Race", "Test", datetime.datetime(1990, 1, 1))
    for book_id in book_ids[:4]:
        service.lend_book_to_member(member_id, book_id)
    log.info("Member %s has 4 unreturned books. Two librarians now lend books %s and %s at the same moment.",
             member_id, book_ids[4], book_ids[5])

    outcomes = two_loans_at_once(service, member_id, book_ids[4], book_ids[5])
    for book_id, outcome in outcomes.items():
        log.info("  book %s: %s", book_id, outcome)
    unreturned = len(service.get_unreturned_books_for_member(member_id))
    held = unreturned <= 5 and not any(o.startswith("ERROR") for o in outcomes.values())
    log.info("The member now has %d unreturned books: %s", unreturned,
             "the limit held." if held else "the 5-book limit was broken (or an error occurred).")
    return held


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    engine = create_engine(DATABASE_URL)
    raise SystemExit(0 if check(sessionmaker(bind=engine)) else 1)
