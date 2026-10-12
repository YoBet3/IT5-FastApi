"""Create the FastAPI app and connect its routes."""

from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import database_connection, initialize_database
from app.errors import AppError
from app.models import Book, BookInput, BorrowInput, Loan, Member, MemberInput

app = FastAPI(title="Campus Library Lending System")


@app.exception_handler(AppError)
async def handle_app_error(request: Request, error: AppError):
    return JSONResponse(status_code=error.status_code, content={"detail": error.message})


@app.get("/")
def home():
    return {"message": "Welcome to the Campus Library Lending System! Visit /docs to try the API."}

@app.get("/books")
def get_books(q: Optional[str] = None):
    result = Book.list_books(database_connection=database_connection, query=q)
    return {"books": result}


@app.get("/books/{book_id}")
def get_book(book_id: int):
    result = Book.get_book(book_id=book_id, database_connection=database_connection)
    return {"book": result}


@app.post("/book", status_code=201)
def create_book(book: BookInput):
    result = Book.create_book(book_input=book, database_connection=database_connection)
    return {"book": result}


@app.put("/book/{book_id}")
def edit_book(book_id: int, book: BookInput):
    result = Book.update_book(
        book_id=book_id, book_input=book, database_connection=database_connection
    )
    return {"book": result}


@app.delete("/book/{book_id}")
def delete_book(book_id: int):
    Book.delete_book(book_id=book_id, database_connection=database_connection)
    return {"message": "Book deleted successfully"}

@app.get("/members")
def get_members():
    result = Member.list_members(database_connection=database_connection)
    return {"members": result}


@app.get("/members/{member_id}")
def get_member(member_id: int):
    result = Member.get_member(member_id=member_id, database_connection=database_connection)
    return {"member": result}


@app.post("/member", status_code=201)
def create_member(member: MemberInput):
    result = Member.create_member(member_input=member, database_connection=database_connection)
    return {"member": result}


@app.put("/member/{member_id}")
def edit_member(member_id: int, member: MemberInput):
    result = Member.update_member(
        member_id=member_id, member_input=member, database_connection=database_connection
    )
    return {"member": result}


@app.delete("/member/{member_id}")
def delete_member(member_id: int):
    Member.delete_member(member_id=member_id, database_connection=database_connection)
    return {"message": "Member deleted successfully"}


@app.post("/loan", status_code=201)
def borrow_book(borrow: BorrowInput):
    result = Loan.borrow_book(borrow_input=borrow, database_connection=database_connection)
    return {"loan": result}


@app.post("/loan/{loan_id}/return")
def return_book(loan_id: int):
    result = Loan.return_book(loan_id=loan_id, database_connection=database_connection)
    return {"loan": result}


@app.get("/loans")
def get_loans(active_only: bool = False, member_id: Optional[int] = None):
    result = Loan.list_loans(
        database_connection=database_connection, active_only=active_only, member_id=member_id
    )
    return {"loans": result}


@app.get("/loans/overdue")
def get_overdue_loans():
    result = Loan.list_overdue(database_connection=database_connection)
    return {"overdue": result}


initialize_database()
