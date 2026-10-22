import psycopg2
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Mock environment variables before importing main
with patch.dict('os.environ', {'DATABASE_URL': 'postgresql://test:test@localhost:5432/testdb'}):
    from main import app, hash_password

client = TestClient(app)


# Builds a mocked get_db_connection whose cursor returns the given rows.
def mock_db(fetchone=None, side_effect=None):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone
    if side_effect is not None:
        mock_cursor.execute.side_effect = side_effect
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_db_conn = MagicMock()
    mock_db_conn.return_value.__enter__.return_value = mock_conn
    return mock_db_conn, mock_cursor


class TestHealth:
    def test_health_returns_healthy(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestCreateUser:
    def test_create_user_hashes_password_and_omits_it_from_response(self):
        mock_db_conn, mock_cursor = mock_db(fetchone={'id': 1, 'name': 'Alice', 'email': 'alice@example.com'})
        with patch('main.get_db_connection', mock_db_conn):
            response = client.post("/users", json={
                "name": "Alice", "email": "alice@example.com", "password": "correct horse battery"
            })

        assert response.status_code == 201
        assert response.json() == {"id": 1, "name": "Alice", "email": "alice@example.com"}
        assert "password" not in response.json()

        stored_password = mock_cursor.execute.call_args[0][1][2]
        assert stored_password != "correct horse battery"
        assert stored_password.startswith("$2b$")

    def test_create_user_duplicate_email_returns_409(self):
        mock_db_conn, _ = mock_db(side_effect=psycopg2.IntegrityError())
        with patch('main.get_db_connection', mock_db_conn):
            response = client.post("/users", json={
                "name": "Alice", "email": "alice@example.com", "password": "correct horse battery"
            })
        assert response.status_code == 409

    @pytest.mark.parametrize("payload", [
        {"name": "Alice", "email": "not-an-email", "password": "correct horse battery"},
        {"name": "Alice", "email": "alice@example.com", "password": "short"},
        {"name": "", "email": "alice@example.com", "password": "correct horse battery"},
    ])
    def test_create_user_rejects_invalid_input(self, payload):
        response = client.post("/users", json=payload)
        assert response.status_code == 422


class TestGetUsers:
    def test_get_user_not_found(self):
        mock_db_conn, _ = mock_db(fetchone=None)
        with patch('main.get_db_connection', mock_db_conn):
            response = client.get("/users/999")
        assert response.status_code == 404


class TestUpdateUser:
    def test_update_without_password_keeps_existing_hash(self):
        mock_db_conn, mock_cursor = mock_db(fetchone={'id': 1, 'name': 'Alicia', 'email': 'alice@example.com'})
        with patch('main.get_db_connection', mock_db_conn):
            response = client.put("/users/1", json={"name": "Alicia", "email": "alice@example.com"})

        assert response.status_code == 200
        sql = mock_cursor.execute.call_args[0][0]
        assert "password" not in sql

    def test_update_with_password_rehashes(self):
        mock_db_conn, mock_cursor = mock_db(fetchone={'id': 1, 'name': 'Alice', 'email': 'alice@example.com'})
        with patch('main.get_db_connection', mock_db_conn):
            response = client.put("/users/1", json={
                "name": "Alice", "email": "alice@example.com", "password": "another long password"
            })

        assert response.status_code == 200
        sql, params = mock_cursor.execute.call_args[0]
        assert "password = %s" in sql
        assert params[2].startswith("$2b$")


class TestHashPassword:
    def test_hash_is_salted(self):
        assert hash_password("same password") != hash_password("same password")
