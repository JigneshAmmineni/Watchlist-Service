import os

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)


# Defines the shape of the users table in the database.
class UsersTable(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(100), nullable=False))
    email: str = Field(sa_column=Column(String(100), unique=True, nullable=False))
    password: str = Field(sa_column=Column(String(255), nullable=False))


# Initializes the database by creating all SQLModel-defined tables if they don't exist.
def init_db():
    SQLModel.metadata.create_all(engine)
    print("Database initialized and tables created.")


# Disposes of the database engine's connection pool.
def close_db_connection():
    engine.dispose()
    print("Database connection closed.")
