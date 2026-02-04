import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Mock environment variables before importing main
with patch.dict('os.environ', {
    'DATABASE_URL': 'postgresql://test:test@localhost:5432/testdb',
    'REDIS_URL': 'redis://localhost:6379'
}):
    with patch('redis.from_url') as mock_redis:
        mock_redis.return_value = MagicMock()
        from main import app, get_db_connection, redis_client

client = TestClient(app)


class TestRootEndpoint:
    def test_root_returns_service_info(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "movie-service"
        assert data["status"] == "running"
        assert data["cache"] == "redis"


class TestHealthEndpoint:
    def test_health_returns_healthy(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestCreateMovie:
    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_create_movie_success(self, mock_redis, mock_db_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'title': 'Inception',
            'director': 'Christopher Nolan',
            'year': 2010,
            'genre': 'Sci-Fi',
            'rating': 8.8
        }
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        movie_data = {
            "title": "Inception",
            "director": "Christopher Nolan",
            "year": 2010,
            "genre": "Sci-Fi",
            "rating": 8.8
        }

        response = client.post("/movies", json=movie_data)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Inception"
        assert data["director"] == "Christopher Nolan"
        assert data["year"] == 2010
        assert data["genre"] == "Sci-Fi"
        assert data["id"] == 1

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_create_movie_caches_result(self, mock_redis, mock_db_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'title': 'Test Movie',
            'director': 'Test Director',
            'year': 2020,
            'genre': 'Action',
            'rating': 7.5
        }
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        movie_data = {
            "title": "Test Movie",
            "director": "Test Director",
            "year": 2020,
            "genre": "Action",
            "rating": 7.5
        }

        client.post("/movies", json=movie_data)

        # Verify cache was set
        mock_redis.setex.assert_called()
        # Verify all movies cache was invalidated
        mock_redis.delete.assert_called()

    def test_create_movie_missing_required_field(self):
        movie_data = {
            "title": "Incomplete Movie",
            "director": "Some Director"
            # Missing year and genre
        }

        response = client.post("/movies", json=movie_data)
        assert response.status_code == 422  # Validation error


class TestGetMovies:
    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_get_movies_from_cache(self, mock_redis, mock_db_conn):
        cached_movies = [
            {'id': 1, 'title': 'Movie 1', 'director': 'Dir 1', 'year': 2020, 'genre': 'Action', 'rating': 8.0},
            {'id': 2, 'title': 'Movie 2', 'director': 'Dir 2', 'year': 2021, 'genre': 'Drama', 'rating': 7.5}
        ]
        mock_redis.get.return_value = json.dumps(cached_movies)

        response = client.get("/movies")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Movie 1"

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_get_movies_cache_miss(self, mock_redis, mock_db_conn):
        mock_redis.get.return_value = None  # Cache miss

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'title': 'Movie 1', 'director': 'Dir 1', 'year': 2020, 'genre': 'Action', 'rating': 8.0}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        response = client.get("/movies")

        assert response.status_code == 200
        # Verify cache was populated
        mock_redis.setex.assert_called()

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_get_movies_by_genre(self, mock_redis, mock_db_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'title': 'Action Movie', 'director': 'Dir', 'year': 2020, 'genre': 'Action', 'rating': 8.0}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        response = client.get("/movies?genre=Action")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["genre"] == "Action"


class TestGetMovieById:
    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_get_movie_from_cache(self, mock_redis, mock_db_conn):
        cached_movie = {'id': 1, 'title': 'Cached Movie', 'director': 'Dir', 'year': 2020, 'genre': 'Action', 'rating': 8.0}
        mock_redis.get.return_value = json.dumps(cached_movie)

        response = client.get("/movies/1")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Cached Movie"
        assert data["id"] == 1

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_get_movie_cache_miss_db_hit(self, mock_redis, mock_db_conn):
        mock_redis.get.return_value = None  # Cache miss

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1, 'title': 'DB Movie', 'director': 'Dir', 'year': 2020, 'genre': 'Action', 'rating': 8.0
        }
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        response = client.get("/movies/1")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "DB Movie"
        # Verify cache was populated
        mock_redis.setex.assert_called()

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_get_movie_not_found(self, mock_redis, mock_db_conn):
        mock_redis.get.return_value = None  # Cache miss

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Not in DB
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        response = client.get("/movies/999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Movie not found"


class TestUpdateMovie:
    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_update_movie_success(self, mock_redis, mock_db_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1, 'title': 'Updated Movie', 'director': 'New Dir', 'year': 2021, 'genre': 'Drama', 'rating': 9.0
        }
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        update_data = {
            "title": "Updated Movie",
            "director": "New Dir",
            "year": 2021,
            "genre": "Drama",
            "rating": 9.0
        }

        response = client.put("/movies/1", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Movie"
        assert data["rating"] == 9.0

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_update_movie_updates_cache(self, mock_redis, mock_db_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1, 'title': 'Updated', 'director': 'Dir', 'year': 2020, 'genre': 'Action', 'rating': 8.0
        }
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        update_data = {
            "title": "Updated",
            "director": "Dir",
            "year": 2020,
            "genre": "Action",
            "rating": 8.0
        }

        client.put("/movies/1", json=update_data)

        # Verify cache was updated and all movies cache invalidated
        assert mock_redis.setex.called
        assert mock_redis.delete.called

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_update_movie_not_found(self, mock_redis, mock_db_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Not found
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        update_data = {
            "title": "Updated",
            "director": "Dir",
            "year": 2020,
            "genre": "Action",
            "rating": 8.0
        }

        response = client.put("/movies/999", json=update_data)

        assert response.status_code == 404
        assert response.json()["detail"] == "Movie not found"


class TestDeleteMovie:
    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_delete_movie_success(self, mock_redis, mock_db_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # Deleted ID
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        response = client.delete("/movies/1")

        assert response.status_code == 200
        assert response.json()["message"] == "Movie deleted successfully"

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_delete_movie_invalidates_cache(self, mock_redis, mock_db_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        client.delete("/movies/1")

        # Verify both individual and all movies cache were invalidated
        assert mock_redis.delete.call_count >= 2

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_delete_movie_not_found(self, mock_redis, mock_db_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Not found
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        response = client.delete("/movies/999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Movie not found"


class TestBatchGetMovies:
    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_batch_get_empty_list(self, mock_redis, mock_db_conn):
        response = client.post("/movies/batch", json={"movie_ids": []})

        assert response.status_code == 200
        assert response.json() == []

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_batch_get_all_from_cache(self, mock_redis, mock_db_conn):
        cached_movies = {
            'movie:1': json.dumps({'id': 1, 'title': 'Movie 1', 'director': 'Dir 1', 'year': 2020, 'genre': 'Action', 'rating': 8.0}),
            'movie:2': json.dumps({'id': 2, 'title': 'Movie 2', 'director': 'Dir 2', 'year': 2021, 'genre': 'Drama', 'rating': 7.5})
        }
        mock_redis.get.side_effect = lambda key: cached_movies.get(key)

        response = client.post("/movies/batch", json={"movie_ids": [1, 2]})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_batch_get_all_from_db(self, mock_redis, mock_db_conn):
        mock_redis.get.return_value = None  # All cache misses

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'title': 'Movie 1', 'director': 'Dir 1', 'year': 2020, 'genre': 'Action', 'rating': 8.0},
            {'id': 2, 'title': 'Movie 2', 'director': 'Dir 2', 'year': 2021, 'genre': 'Drama', 'rating': 7.5}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        response = client.post("/movies/batch", json={"movie_ids": [1, 2]})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_batch_get_mixed_cache_and_db(self, mock_redis, mock_db_conn):
        # Movie 1 in cache, Movie 2 not in cache
        def get_from_cache(key):
            if key == 'movie:1':
                return json.dumps({'id': 1, 'title': 'Cached Movie', 'director': 'Dir', 'year': 2020, 'genre': 'Action', 'rating': 8.0})
            return None

        mock_redis.get.side_effect = get_from_cache

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 2, 'title': 'DB Movie', 'director': 'Dir 2', 'year': 2021, 'genre': 'Drama', 'rating': 7.5}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        response = client.post("/movies/batch", json={"movie_ids": [1, 2]})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_batch_get_caches_db_results(self, mock_redis, mock_db_conn):
        mock_redis.get.return_value = None  # Cache miss

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'title': 'Movie 1', 'director': 'Dir', 'year': 2020, 'genre': 'Action', 'rating': 8.0}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        client.post("/movies/batch", json={"movie_ids": [1]})

        # Verify that fetched movies were cached
        mock_redis.setex.assert_called()

    @patch('main.get_db_connection')
    @patch('main.redis_client')
    def test_batch_get_nonexistent_ids(self, mock_redis, mock_db_conn):
        mock_redis.get.return_value = None  # Cache miss

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # No movies found
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value.__enter__.return_value = mock_conn

        response = client.post("/movies/batch", json={"movie_ids": [999, 1000]})

        assert response.status_code == 200
        assert response.json() == []


class TestMovieValidation:
    def test_movie_year_must_be_integer(self):
        movie_data = {
            "title": "Test",
            "director": "Dir",
            "year": "not a number",
            "genre": "Action"
        }
        response = client.post("/movies", json=movie_data)
        assert response.status_code == 422

    def test_movie_rating_optional(self):
        with patch('main.get_db_connection') as mock_db_conn, \
             patch('main.redis_client') as mock_redis:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                'id': 1, 'title': 'No Rating', 'director': 'Dir', 'year': 2020, 'genre': 'Action', 'rating': None
            }
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db_conn.return_value.__enter__.return_value = mock_conn

            movie_data = {
                "title": "No Rating",
                "director": "Dir",
                "year": 2020,
                "genre": "Action"
            }

            response = client.post("/movies", json=movie_data)
            assert response.status_code == 200
