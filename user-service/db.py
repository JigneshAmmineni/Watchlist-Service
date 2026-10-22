import os

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL")

# SQLAlchemy 2.1+ defaults "postgresql://" to psycopg (v3); name the psycopg2 driver explicitly
# so the ORM and the raw psycopg2 connections in main.py share one driver.
engine = create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1))


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
