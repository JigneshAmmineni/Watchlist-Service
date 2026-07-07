import os
from decimal import Decimal

from sqlalchemy import Column, Numeric, String
from sqlmodel import Field, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)


# Defines the shape of the movies table in the database.
class MoviesTable(SQLModel, table=True):
    __tablename__ = "movies"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(sa_column=Column(String(200), nullable=False))
    director: str = Field(sa_column=Column(String(100), nullable=False))
    year: int
    genre: str = Field(sa_column=Column(String(50), nullable=False))
    rating: Decimal | None = Field(default=None, sa_column=Column(Numeric(3, 1)))


# Initializes the database by creating all SQLModel-defined tables if they don't exist.
def init_db():
    SQLModel.metadata.create_all(engine)
    print("Database initialized and tables created.")


# Disposes of the database engine's connection pool.
def close_db_connection():
    engine.dispose()
    print("Database connection closed.")
