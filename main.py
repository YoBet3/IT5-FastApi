"""FastAPI application: endpoints only. Logic lives in repositories/services."""
import os
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .database import Database
from .errors import AppError
from .repositories import BookRepository, MemberRepository
from .schemas import BookInput, BookUpdate, BorrowInput, MemberInput, MemberUpdate
from .services import LoanService

db = Database(os.getenv("LIBRARY_DB", "library.db"))
books = BookRepository(db)
members = MemberRepository(db)
loans = LoanService(db, books, members)

app = FastAPI(
    title="Campus Library Lending System",
    description="Tracks books, members and borrowing/returning with due dates and fines.",
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/")
def root():
    return {"message": "Welcome to the Campus Library Lending System"}


# ---------------- Books ----------------
@app.post("/books", status_code=201)
def create_book(book: BookInput):
    return books.create(book.title, book.author, book.copies)


@app.get("/books")
def list_books(q: Optional[str] = None):
    return books.search(q)


@app.get("/books/{book_id}")
def get_book(book_id: int):
    return books.get(book_id)


@app.put("/books/{book_id}")
def update_book(book_id: int, data: BookUpdate):
    return books.update(book_id, data.title, data.author, data.copies)


@app.delete("/books/{book_id}")
def delete_book(book_id: int):
    books.delete(book_id)
    return {"message": f"Book {book_id} deleted"}


# ---------------- Members ----------------
@app.post("/members", status_code=201)
def create_member(member: MemberInput):
    return members.create(member.name, member.email)


@app.get("/members")
def list_members():
    return members.list_all()


@app.get("/members/{member_id}")
def get_member(member_id: int):
    return members.get(member_id)


@app.put("/members/{member_id}")
def update_member(member_id: int, data: MemberUpdate):
    return members.update(member_id, data.name, data.email)


@app.delete("/members/{member_id}")
def delete_member(member_id: int):
    members.delete(member_id)
    return {"message": f"Member {member_id} deleted"}


# ---------------- Loans (transactions) ----------------
@app.post("/loans/borrow", status_code=201)
def borrow_book(data: BorrowInput):
    return loans.borrow(data.book_id, data.member_id)


@app.post("/loans/{loan_id}/return")
def return_book(loan_id: int):
    return loans.return_book(loan_id)


@app.get("/loans")
def list_loans(active_only: bool = False, member_id: Optional[int] = None):
    return loans.list_loans(active_only, member_id)


@app.get("/loans/overdue")
def overdue_loans():
    return loans.overdue()
