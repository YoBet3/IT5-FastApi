"""Data models used to validate API input and output.

Same pattern as the starter project: an "Input" class validates what the
client sends, a child class adds the database id, and static methods hold
the SQL for that table.
"""
import sqlite3
from datetime import datetime, timedelta
from typing import ClassVar, Optional

from pydantic import BaseModel, Field

from app.errors import ConflictError, NotFoundError

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class BookInput(BaseModel):
    """Fields sent when creating or updating a book."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    copies: int = Field(ge=1)

    @staticmethod
    def list_books(database_connection, query: Optional[str] = None):
        sql = "SELECT id, title, author, copies, available FROM books"
        params: tuple = ()
        if query:
            sql += " WHERE title LIKE ? OR author LIKE ?"
            params = (f"%{query}%", f"%{query}%")
        with database_connection() as connection:
            rows = connection.execute(sql + " ORDER BY title", params).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_book(book_id, database_connection):
        with database_connection() as connection:
            row = connection.execute(
                "SELECT id, title, author, copies, available FROM books WHERE id = ?",
                (book_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Book {book_id} not found")
        return dict(row)

    @staticmethod
    def create_book(book_input, database_connection):
        with database_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO books (title, author, copies, available) VALUES (?, ?, ?, ?)",
                (book_input.title, book_input.author, book_input.copies, book_input.copies),
            )
            new_id = cursor.lastrowid
        return BookInput.get_book(new_id, database_connection)

    @staticmethod
    def update_book(book_id, book_input, database_connection):
        book = BookInput.get_book(book_id, database_connection)
        on_loan = book["copies"] - book["available"]
        if book_input.copies < on_loan:
            raise ConflictError(
                f"Cannot set copies to {book_input.copies}: {on_loan} copies are on loan"
            )
        with database_connection() as connection:
            connection.execute(
                "UPDATE books SET title = ?, author = ?, copies = ?, available = ? WHERE id = ?",
                (
                    book_input.title,
                    book_input.author,
                    book_input.copies,
                    book_input.copies - on_loan,
                    book_id,
                ),
            )
        return BookInput.get_book(book_id, database_connection)

    @staticmethod
    def delete_book(book_id, database_connection):
        BookInput.get_book(book_id, database_connection)  # 404 if missing
        try:
            with database_connection() as connection:
                connection.execute("DELETE FROM books WHERE id = ?", (book_id,))
        except sqlite3.IntegrityError:
            raise ConflictError(f"Book {book_id} has loan records and cannot be deleted")


class Book(BookInput):
    """A book record returned by the API."""

    id: int
    available: int


class MemberInput(BaseModel):
    """Fields sent when creating or updating a member."""

    name: str = Field(min_length=1)
    email: str = Field(pattern=EMAIL_PATTERN)

    @staticmethod
    def list_members(database_connection):
        with database_connection() as connection:
            rows = connection.execute(
                "SELECT id, name, email FROM members ORDER BY name"
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_member(member_id, database_connection):
        with database_connection() as connection:
            row = connection.execute(
                "SELECT id, name, email FROM members WHERE id = ?", (member_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Member {member_id} not found")
        return dict(row)

    @staticmethod
    def create_member(member_input, database_connection):
        try:
            with database_connection() as connection:
                cursor = connection.execute(
                    "INSERT INTO members (name, email) VALUES (?, ?)",
                    (member_input.name, member_input.email),
                )
                new_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ConflictError(f"A member with email {member_input.email} already exists")
        return MemberInput.get_member(new_id, database_connection)

    @staticmethod
    def update_member(member_id, member_input, database_connection):
        MemberInput.get_member(member_id, database_connection)
        try:
            with database_connection() as connection:
                connection.execute(
                    "UPDATE members SET name = ?, email = ? WHERE id = ?",
                    (member_input.name, member_input.email, member_id),
                )
        except sqlite3.IntegrityError:
            raise ConflictError(f"A member with email {member_input.email} already exists")
        return MemberInput.get_member(member_id, database_connection)

    @staticmethod
    def delete_member(member_id, database_connection):
        MemberInput.get_member(member_id, database_connection)  # 404 if missing
        try:
            with database_connection() as connection:
                connection.execute("DELETE FROM members WHERE id = ?", (member_id,))
        except sqlite3.IntegrityError:
            raise ConflictError(f"Member {member_id} has loan records and cannot be deleted")


class Member(MemberInput):
    """A member record returned by the API."""

    id: int


class BorrowInput(BaseModel):
    """Fields sent when a member borrows a book."""

    book_id: int
    member_id: int

    # Library rules, kept in one place so they are easy to change.
    LOAN_DAYS: ClassVar[int] = 7
    MAX_ACTIVE_LOANS: ClassVar[int] = 3
    FINE_PER_DAY: ClassVar[float] = 5.0

    @staticmethod
    def borrow_book(borrow_input, database_connection, now: Optional[datetime] = None):
        """TRANSACTION: check the rules, reduce stock and record the loan.

        All of it happens in one connection, so a failure at any step
        rolls everything back and no half-finished loan is saved.
        """
        now = now or datetime.now()
        due = now + timedelta(days=BorrowInput.LOAN_DAYS)
        with database_connection() as connection:
            if connection.execute(
                "SELECT 1 FROM books WHERE id = ?", (borrow_input.book_id,)
            ).fetchone() is None:
                raise NotFoundError(f"Book {borrow_input.book_id} not found")
            if connection.execute(
                "SELECT 1 FROM members WHERE id = ?", (borrow_input.member_id,)
            ).fetchone() is None:
                raise NotFoundError(f"Member {borrow_input.member_id} not found")

            active = connection.execute(
                "SELECT COUNT(*) FROM loans WHERE member_id = ? AND returned_at IS NULL",
                (borrow_input.member_id,),
            ).fetchone()[0]
            if active >= BorrowInput.MAX_ACTIVE_LOANS:
                raise ConflictError(
                    f"Member already has {BorrowInput.MAX_ACTIVE_LOANS} active loans (the limit)"
                )
            if connection.execute(
                "SELECT 1 FROM loans WHERE member_id = ? AND book_id = ? AND returned_at IS NULL",
                (borrow_input.member_id, borrow_input.book_id),
            ).fetchone():
                raise ConflictError("Member has already borrowed this book and not returned it")

            cursor = connection.execute(
                "UPDATE books SET available = available - 1 WHERE id = ? AND available > 0",
                (borrow_input.book_id,),
            )
            if cursor.rowcount == 0:
                raise ConflictError("No copies of this book are currently available")

            cursor = connection.execute(
                "INSERT INTO loans (book_id, member_id, borrowed_at, due_date) VALUES (?, ?, ?, ?)",
                (
                    borrow_input.book_id,
                    borrow_input.member_id,
                    now.isoformat(timespec="seconds"),
                    due.isoformat(timespec="seconds"),
                ),
            )
            new_id = cursor.lastrowid
        return BorrowInput.get_loan(new_id, database_connection)

    @staticmethod
    def return_book(loan_id, database_connection, now: Optional[datetime] = None):
        """TRANSACTION: close the loan, add the copy back, compute any fine."""
        now = now or datetime.now()
        with database_connection() as connection:
            loan = connection.execute(
                "SELECT * FROM loans WHERE id = ?", (loan_id,)
            ).fetchone()
            if loan is None:
                raise NotFoundError(f"Loan {loan_id} not found")
            if loan["returned_at"] is not None:
                raise ConflictError("This loan has already been returned")
            overdue_days = max(0, (now - datetime.fromisoformat(loan["due_date"])).days)
            fine = overdue_days * BorrowInput.FINE_PER_DAY
            connection.execute(
                "UPDATE loans SET returned_at = ?, fine = ? WHERE id = ?",
                (now.isoformat(timespec="seconds"), fine, loan_id),
            )
            connection.execute(
                "UPDATE books SET available = available + 1 WHERE id = ?",
                (loan["book_id"],),
            )
        return BorrowInput.get_loan(loan_id, database_connection)

    @staticmethod
    def get_loan(loan_id, database_connection):
        with database_connection() as connection:
            row = connection.execute(
                "SELECT * FROM loans WHERE id = ?", (loan_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Loan {loan_id} not found")
        return dict(row)

    @staticmethod
    def list_loans(database_connection, active_only=False, member_id=None):
        """Joins loans with books and members to show readable names."""
        sql = (
            "SELECT l.*, b.title AS book_title, m.name AS member_name "
            "FROM loans l JOIN books b ON b.id = l.book_id "
            "JOIN members m ON m.id = l.member_id WHERE 1 = 1"
        )
        params: list = []
        if active_only:
            sql += " AND l.returned_at IS NULL"
        if member_id is not None:
            sql += " AND l.member_id = ?"
            params.append(member_id)
        with database_connection() as connection:
            rows = connection.execute(sql + " ORDER BY l.id DESC", params).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def list_overdue(database_connection, now: Optional[datetime] = None):
        now = now or datetime.now()
        result = []
        for loan in BorrowInput.list_loans(database_connection, active_only=True):
            due = datetime.fromisoformat(loan["due_date"])
            if now > due:
                loan["days_overdue"] = (now - due).days
                loan["fine_so_far"] = loan["days_overdue"] * BorrowInput.FINE_PER_DAY
                result.append(loan)
        return result


class Loan(BorrowInput):
    """A loan record returned by the API."""

    id: int
    borrowed_at: str
    due_date: str
    returned_at: Optional[str] = None
    fine: float = 0
