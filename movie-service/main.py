from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import redis
import json

app = FastAPI(title="Movie Service")

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

# Initialize Redis client
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
CACHE_TTL = 3600  # 1 hour

class Movie(BaseModel):
    id: Optional[int] = None
    title: str
    director: str
    year: int
    genre: str
    rating: Optional[float] = None

class BatchMovieRequest(BaseModel):
    movie_ids: List[int]

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

# Initializes the database by creating the movies table if it doesn't exist.
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    director VARCHAR(100) NOT NULL,
                    year INTEGER NOT NULL,
                    genre VARCHAR(50) NOT NULL,
                    rating DECIMAL(3, 1)
                )
            """)

# Generates a Redis cache key for a specific movie by ID.
def get_cache_key(movie_id: int) -> str:
    return f"movie:{movie_id}"

# Returns the Redis cache key for the all-movies list.
def get_all_movies_cache_key() -> str:
    return "movies:all"

# Runs on application startup to initialize the database.
@app.on_event("startup")
async def startup_event():
    init_db()

# Returns service name, status, and cache info.
@app.get("/")
async def root():
    return {"service": "movie-service", "status": "running", "cache": "redis"}

# Health check endpoint for monitoring and load balancers.
@app.get("/health")
async def health():
    return {"status": "healthy"}

# Creates a new movie, caches it in Redis, and invalidates the all-movies cache.
@app.post("/movies", response_model=Movie)
async def create_movie(movie: Movie):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO movies (title, director, year, genre, rating) VALUES (%s, %s, %s, %s, %s) RETURNING *",
                (movie.title, movie.director, movie.year, movie.genre, movie.rating)
            )
            result = cur.fetchone()
            movie_data = dict(result)

            # Cache-aside: Store in cache after creation
            cache_key = get_cache_key(movie_data['id'])
            redis_client.setex(cache_key, CACHE_TTL, json.dumps(movie_data, default=str))

            # Invalidate all movies cache
            redis_client.delete(get_all_movies_cache_key())

            return movie_data

# Retrieves multiple movies by IDs using cache-aside pattern for efficiency.
@app.post("/movies/batch", response_model=List[Movie])
async def get_movies_batch(request: BatchMovieRequest):
    if not request.movie_ids:
        return []

    movies = []
    uncached_ids = []

    # Cache-aside: Check cache first for each movie
    for movie_id in request.movie_ids:
        cache_key = get_cache_key(movie_id)
        cached_data = redis_client.get(cache_key)

        if cached_data:
            movies.append(json.loads(cached_data))
        else:
            uncached_ids.append(movie_id)

    # Fetch uncached movies from database in a single query
    if uncached_ids:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM movies WHERE id = ANY(%s)", (uncached_ids,))
                results = cur.fetchall()

                for row in results:
                    movie_data = dict(row)
                    movies.append(movie_data)

                    # Cache the newly fetched movie
                    cache_key = get_cache_key(movie_data['id'])
                    redis_client.setex(cache_key, CACHE_TTL, json.dumps(movie_data, default=str))

    return movies

# Retrieves all movies or filters by genre. Uses cache for unfiltered queries.
@app.get("/movies", response_model=List[Movie])
async def get_movies(genre: Optional[str] = None):
    # For filtered queries, skip cache
    if genre:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM movies WHERE genre = %s", (genre,))
                results = cur.fetchall()
                return [dict(row) for row in results]

    # Cache-aside: Check cache first for all movies
    cache_key = get_all_movies_cache_key()
    cached_data = redis_client.get(cache_key)

    if cached_data:
        return json.loads(cached_data)

    # Cache miss: Fetch from database
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM movies")
            results = cur.fetchall()
            movies = [dict(row) for row in results]

            # Store in cache
            redis_client.setex(cache_key, CACHE_TTL, json.dumps(movies, default=str))

            return movies

# Retrieves a single movie by ID using cache-aside pattern. Returns 404 if not found.
@app.get("/movies/{movie_id}", response_model=Movie)
async def get_movie(movie_id: int):
    # Cache-aside: Check cache first
    cache_key = get_cache_key(movie_id)
    cached_data = redis_client.get(cache_key)

    if cached_data:
        return json.loads(cached_data)

    # Cache miss: Fetch from database
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Movie not found")

            movie_data = dict(result)

            # Store in cache
            redis_client.setex(cache_key, CACHE_TTL, json.dumps(movie_data, default=str))

            return movie_data

# Updates a movie, refreshes its cache entry, and invalidates the all-movies cache.
@app.put("/movies/{movie_id}", response_model=Movie)
async def update_movie(movie_id: int, movie: Movie):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "UPDATE movies SET title = %s, director = %s, year = %s, genre = %s, rating = %s WHERE id = %s RETURNING *",
                (movie.title, movie.director, movie.year, movie.genre, movie.rating, movie_id)
            )
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Movie not found")

            movie_data = dict(result)

            # Cache-aside: Update cache after database update
            cache_key = get_cache_key(movie_id)
            redis_client.setex(cache_key, CACHE_TTL, json.dumps(movie_data, default=str))

            # Invalidate all movies cache
            redis_client.delete(get_all_movies_cache_key())

            return movie_data

# Deletes a movie, removes it from cache, and invalidates the all-movies cache.
@app.delete("/movies/{movie_id}")
async def delete_movie(movie_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM movies WHERE id = %s RETURNING id", (movie_id,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Movie not found")

            # Cache-aside: Remove from cache after deletion
            cache_key = get_cache_key(movie_id)
            redis_client.delete(cache_key)

            # Invalidate all movies cache
            redis_client.delete(get_all_movies_cache_key())

            return {"message": "Movie deleted successfully"}
