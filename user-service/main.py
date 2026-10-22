from contextlib import asynccontextmanager, contextmanager
from typing import List, Optional
import os

import bcrypt
import psycopg2
from fastapi import FastAPI, HTTPException
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, EmailStr, Field

from db import close_db_connection, init_db

DATABASE_URL = os.getenv("DATABASE_URL")


# Initializes the database on startup and releases connections on shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    close_db_connection()


app = FastAPI(title="User Service", lifespan=lifespan)


# Request body for creating a user. The password is hashed before storage.
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=100)
    password: str = Field(min_length=8, max_length=72)


# Request body for updating a user. Omit the password to keep the current one.
class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=100)
    password: Optional[str] = Field(default=None, min_length=8, max_length=72)


# Public representation of a user. The password hash is never returned.
class UserOut(BaseModel):
    id: int
    name: str
    email: str


# Context manager that provides a database connection with automatic commit/rollback.
@contextmanager
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Hashes a plaintext password with bcrypt so the original is never stored.
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Returns service name and status information.
@app.get("/")
async def root():
    return {"service": "user-service", "status": "running"}


# Health check endpoint for monitoring and load balancers.
@app.get("/health")
async def health():
    return {"status": "healthy"}


# Creates a new user with a hashed password. Returns 409 if the email is already taken.
@app.post("/users", response_model=UserOut, status_code=201)
async def create_user(user: UserCreate):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO users (name, email, password) VALUES (%s, %s, %s) RETURNING id, name, email",
                    (user.name, user.email, hash_password(user.password)),
                )
                return dict(cur.fetchone())
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")


# Retrieves all users from the database.
@app.get("/users", response_model=List[UserOut])
async def get_users():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name, email FROM users ORDER BY id")
            return [dict(row) for row in cur.fetchall()]


# Retrieves a single user by ID. Returns 404 if not found.
@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            return dict(result)


# Updates a user's details, re-hashing the password only if a new one is given.
@app.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, user: UserUpdate):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if user.password is not None:
                    cur.execute(
                        "UPDATE users SET name = %s, email = %s, password = %s WHERE id = %s RETURNING id, name, email",
                        (user.name, user.email, hash_password(user.password), user_id),
                    )
                else:
                    cur.execute(
                        "UPDATE users SET name = %s, email = %s WHERE id = %s RETURNING id, name, email",
                        (user.name, user.email, user_id),
                    )
                result = cur.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="User not found")
                return dict(result)
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")


# Deletes a user by ID. Returns 404 if not found.
@app.delete("/users/{user_id}")
async def delete_user(user_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            return {"message": "User deleted successfully"}
