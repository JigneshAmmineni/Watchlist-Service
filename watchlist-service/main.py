from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import httpx

app = FastAPI(title="Watchlist Service")

DATABASE_URL = os.getenv("DATABASE_URL")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
MOVIE_SERVICE_URL = os.getenv("MOVIE_SERVICE_URL")

class WatchlistEntry(BaseModel):
    id: Optional[int] = None
    user_id: int
    movie_id: int

class WatchlistResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    movie_title: Optional[str] = None
    movie_director: Optional[str] = None
    movie_year: Optional[int] = None

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

# Initializes the database by creating the watchlist table and indexes if they don't exist.
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    movie_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, movie_id)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON watchlist(user_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_watchlist_movie_id ON watchlist(movie_id)
            """)

# Validates that a user exists by calling the user-service API.
async def validate_user_exists(user_id: int) -> bool:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{USER_SERVICE_URL}/users/{user_id}")
            return response.status_code == 200
        except Exception:
            return False

# Validates that a movie exists by calling the movie-service API.
async def validate_movie_exists(movie_id: int) -> bool:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MOVIE_SERVICE_URL}/movies/{movie_id}")
            return response.status_code == 200
        except Exception:
            return False

# Fetches full movie details from the movie-service API.
async def get_movie_details(movie_id: int) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MOVIE_SERVICE_URL}/movies/{movie_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

# Runs on application startup to initialize the database.
@app.on_event("startup")
async def startup_event():
    init_db()

# Returns service name and status information.
@app.get("/")
async def root():
    return {"service": "watchlist-service", "status": "running"}

# Health check endpoint for monitoring and load balancers.
@app.get("/health")
async def health():
    return {"status": "healthy"}

# Adds a movie to a user's watchlist after validating both exist. Returns 409 if duplicate.
@app.post("/watchlist", response_model=WatchlistEntry)
async def add_to_watchlist(entry: WatchlistEntry):
    # Validate that user exists
    if not await validate_user_exists(entry.user_id):
        raise HTTPException(status_code=404, detail=f"User {entry.user_id} not found")

    # Validate that movie exists
    if not await validate_movie_exists(entry.movie_id):
        raise HTTPException(status_code=404, detail=f"Movie {entry.movie_id} not found")

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO watchlist (user_id, movie_id) VALUES (%s, %s) RETURNING *",
                    (entry.user_id, entry.movie_id)
                )
                result = cur.fetchone()
                return dict(result)
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=409, detail="Movie already in watchlist")

# Retrieves a user's watchlist with movie details enriched from movie-service.
@app.get("/watchlist/user/{user_id}", response_model=List[WatchlistResponse])
async def get_user_watchlist(user_id: int):
    # Validate that user exists
    if not await validate_user_exists(user_id):
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM watchlist WHERE user_id = %s", (user_id,))
            results = cur.fetchall()
            watchlist = []

            for row in results:
                entry = dict(row)
                # Fetch movie details
                movie = await get_movie_details(entry['movie_id'])
                if movie:
                    entry['movie_title'] = movie.get('title')
                    entry['movie_director'] = movie.get('director')
                    entry['movie_year'] = movie.get('year')
                watchlist.append(entry)

            return watchlist

# Exports a user's watchlist as full movie objects using batch fetch from movie-service.
@app.get("/watchlist/user/{user_id}/export")
async def export_user_watchlist(user_id: int):
    # Validate that user exists
    if not await validate_user_exists(user_id):
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Get all movie_ids from user's watchlist
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT movie_id FROM watchlist WHERE user_id = %s", (user_id,))
            results = cur.fetchall()
            movie_ids = [row['movie_id'] for row in results]

    # If watchlist is empty, return empty list
    if not movie_ids:
        return []

    # Call movie-service batch endpoint to get full movie objects
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{MOVIE_SERVICE_URL}/movies/batch",
                json={"movie_ids": movie_ids}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch movies: {str(e)}")

# Retrieves all watchlist entries for a specific movie (who is watching it).
@app.get("/watchlist/movie/{movie_id}", response_model=List[WatchlistEntry])
async def get_movie_watchers(movie_id: int):
    # Validate that movie exists
    if not await validate_movie_exists(movie_id):
        raise HTTPException(status_code=404, detail=f"Movie {movie_id} not found")

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM watchlist WHERE movie_id = %s", (movie_id,))
            results = cur.fetchall()
            return [dict(row) for row in results]

# Removes a watchlist entry by its ID. Returns 404 if not found.
@app.delete("/watchlist/{watchlist_id}")
async def remove_from_watchlist(watchlist_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM watchlist WHERE id = %s RETURNING id", (watchlist_id,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Watchlist entry not found")
            return {"message": "Removed from watchlist successfully"}

# Removes a specific movie from a user's watchlist. Returns 404 if not found.
@app.delete("/watchlist/user/{user_id}/movie/{movie_id}")
async def remove_movie_from_user_watchlist(user_id: int, movie_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM watchlist WHERE user_id = %s AND movie_id = %s RETURNING id",
                (user_id, movie_id)
            )
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Watchlist entry not found")
            return {"message": "Removed from watchlist successfully"}

# Checks if a specific movie is in a user's watchlist.
@app.get("/watchlist/user/{user_id}/movie/{movie_id}")
async def check_in_watchlist(user_id: int, movie_id: int):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM watchlist WHERE user_id = %s AND movie_id = %s",
                (user_id, movie_id)
            )
            result = cur.fetchone()
            return {
                "in_watchlist": result is not None,
                "entry": dict(result) if result else None
            }
