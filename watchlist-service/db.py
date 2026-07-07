import os
from datetime import datetime

from sqlalchemy import TIMESTAMP, Column, Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)


# Defines the shape of the watchlist table in the database.
class WatchlistTable(SQLModel, table=True):
    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id"),
        Index("idx_watchlist_user_id", "user_id"),
        Index("idx_watchlist_movie_id", "movie_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int
    movie_id: int
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP")),
    )


# Initializes the database by creating all SQLModel-defined tables if they don't exist.
def init_db():
    SQLModel.metadata.create_all(engine)
    print("Database initialized and tables created.")


# Disposes of the database engine's connection pool.
def close_db_connection():
    engine.dispose()
    print("Database connection closed.")
