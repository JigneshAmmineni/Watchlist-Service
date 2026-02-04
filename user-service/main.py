from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

app = FastAPI(title="User Service")

DATABASE_URL = os.getenv("DATABASE_URL")

class User(BaseModel):
    id: Optional[int] = None
    name: str
    email: str
    password: str

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

# Initializes the database by creating the users table if it doesn't exist.
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL
                )
            """)

# Runs on application startup to initialize the database.
@app.on_event("startup")
async def startup_event():
    init_db()

# Returns service name and status information.
@app.get("/")
async def root():
    return {"service": "user-service", "status": "running"}

# Health check endpoint for monitoring and load balancers.
@app.get("/health")
async def health():
    return {"status": "healthy"}

# Creates a new user in the database and returns the created user.
@app.post("/users", response_model=User)
async def create_user(user: User):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s) RETURNING *",
                (user.name, user.email, user.password)
            )
            result = cur.fetchone()
            return dict(result)

# Retrieves all users from the database.
@app.get("/users", response_model=List[User])
async def get_users():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users")
            results = cur.fetchall()
            return [dict(row) for row in results]

# Retrieves a single user by ID. Returns 404 if not found.
@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            return dict(result)

# Updates an existing user's details. Returns 404 if not found.
@app.put("/users/{user_id}", response_model=User)
async def update_user(user_id: int, user: User):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "UPDATE users SET name = %s, email = %s, password = %s WHERE id = %s RETURNING *",
                (user.name, user.email, user.password, user_id)
            )
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            return dict(result)

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
