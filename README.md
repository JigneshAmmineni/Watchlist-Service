# Movie Watchlist Microservices System

A small, fully runnable microservices demo: three FastAPI services (users, movies, watchlists) behind an nginx API gateway, each with its own PostgreSQL database, a Redis cache-aside layer for the movie catalog, and a single-page frontend. One `docker compose up` brings up all eight containers.

> **About this project.** This repo was my Claude Code tutorial: I recreated a project I had previously coded by hand and knew every line of, so I could judge how Claude Code works and what it can and cannot do. The `CLAUDE.md` file and `.claude/commands/` folder are part of that experiment.

> **Demo scope.** There is no authentication or authorization; every endpoint is open. Passwords are bcrypt-hashed and never returned by the API, but this is a learning project, not a production service.

## Architecture Overview

This system consists of 3 microservices:

1. **User Service** - Manages user accounts and authentication
2. **Movie Service** - Manages movie catalog with Redis caching
3. **Watchlist Service** - Manages user-movie relationships (watchlists)

Additional components:
- **Nginx API Gateway** - Routes requests to appropriate services
- **PostgreSQL Databases** - Separate database for each service
- **Redis Cache** - Caching layer for movie service

## Prerequisites

- Docker
- Docker Compose
- curl or Postman (for testing)

## Quick Start

### 1. Start All Services

```bash
docker compose up --build
```

This will start:
- API Gateway on port 8080
- User Service with its PostgreSQL database
- Movie Service with its PostgreSQL database and Redis cache
- Watchlist Service with its PostgreSQL database
- Redis on port 6379

### 2. Verify Services are Running

```bash
# Check API Gateway
curl http://localhost:8080/

# Check individual service health
curl http://localhost:8080/api/health/users
curl http://localhost:8080/api/health/movies
curl http://localhost:8080/api/health/watchlist
```

## API Endpoints

All requests go through the API Gateway at `http://localhost:8080`

### User Service (`/api/users`)

#### Create a User
```bash
curl -X POST http://localhost:8080/api/users \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com", "password": "password123"}'
```
Returns `201` with `id`, `name`, and `email`. Passwords must be at least 8 characters; the hash is never returned. A duplicate email returns `409`.

#### Get All Users
```bash
curl http://localhost:8080/api/users
```

#### Get User by ID
```bash
curl http://localhost:8080/api/users/1
```

#### Update User
```bash
curl -X PUT http://localhost:8080/api/users/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe", "email": "jane@example.com", "password": "newpass123"}'
```
Omit `password` to keep the current one.

#### Delete User
```bash
curl -X DELETE http://localhost:8080/api/users/1
```

### Movie Service (`/api/movies`)

#### Create a Movie
```bash
curl -X POST http://localhost:8080/api/movies \
  -H "Content-Type: application/json" \
  -d '{"title": "The Shawshank Redemption", "director": "Frank Darabont", "year": 1994, "genre": "Drama", "rating": 9.3}'
```

#### Get All Movies
```bash
curl http://localhost:8080/api/movies
```

#### Get Movies by Genre
```bash
curl "http://localhost:8080/api/movies?genre=Drama"
```

#### Get Movie by ID
```bash
curl http://localhost:8080/api/movies/1
```

#### Batch Get Movies (up to 100 IDs)
```bash
curl -X POST http://localhost:8080/api/movies/batch \
  -H "Content-Type: application/json" \
  -d '{"movie_ids": [1, 2, 3]}'
```

#### Update Movie
```bash
curl -X PUT http://localhost:8080/api/movies/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "The Shawshank Redemption", "director": "Frank Darabont", "year": 1994, "genre": "Drama", "rating": 9.5}'
```

#### Delete Movie
```bash
curl -X DELETE http://localhost:8080/api/movies/1
```

### Watchlist Service (`/api/watchlist`)

#### Add Movie to Watchlist
```bash
curl -X POST http://localhost:8080/api/watchlist \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "movie_id": 1}'
```

#### Get User's Watchlist (with movie details)
```bash
curl http://localhost:8080/api/watchlist/user/1
```

#### Export User's Watchlist (full movie objects)
```bash
curl http://localhost:8080/api/watchlist/user/1/export
```

#### Get Users Who Added a Movie
```bash
curl http://localhost:8080/api/watchlist/movie/1
```

#### Remove from Watchlist by Entry ID
```bash
curl -X DELETE http://localhost:8080/api/watchlist/1
```

#### Remove Specific Movie from User's Watchlist
```bash
curl -X DELETE http://localhost:8080/api/watchlist/user/1/movie/1
```

#### Check if Movie is in User's Watchlist
```bash
curl http://localhost:8080/api/watchlist/user/1/movie/1
```

## Complete Example Workflow

```bash
# 1. Create a user
curl -X POST http://localhost:8080/api/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com", "password": "pass123"}'

# 2. Create some movies
curl -X POST http://localhost:8080/api/movies \
  -H "Content-Type: application/json" \
  -d '{"title": "Inception", "director": "Christopher Nolan", "year": 2010, "genre": "Sci-Fi", "rating": 8.8}'

curl -X POST http://localhost:8080/api/movies \
  -H "Content-Type: application/json" \
  -d '{"title": "The Dark Knight", "director": "Christopher Nolan", "year": 2008, "genre": "Action", "rating": 9.0}'

curl -X POST http://localhost:8080/api/movies \
  -H "Content-Type: application/json" \
  -d '{"title": "Interstellar", "director": "Christopher Nolan", "year": 2014, "genre": "Sci-Fi", "rating": 8.6}'

# 3. Add movies to user's watchlist
curl -X POST http://localhost:8080/api/watchlist \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "movie_id": 1}'

curl -X POST http://localhost:8080/api/watchlist \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "movie_id": 2}'

curl -X POST http://localhost:8080/api/watchlist \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "movie_id": 3}'

# 4. Get user's watchlist with basic movie info
curl http://localhost:8080/api/watchlist/user/1

# 5. Export user's complete watchlist (full movie objects)
curl http://localhost:8080/api/watchlist/user/1/export

# 6. Test batch movie retrieval
curl -X POST http://localhost:8080/api/movies/batch \
  -H "Content-Type: application/json" \
  -d '{"movie_ids": [1, 2, 3]}'
```

## Technical Features

### Redis Cache-Aside Pattern (Movie Service)
The movie service implements a cache-aside pattern:
- **Read**: Check cache first, fetch from DB on miss, then cache
- **Write**: Update DB, then update cache
- **Delete**: Remove from DB, then invalidate cache
- **TTL**: 1 hour (3600 seconds)

### Microservice Communication
- Watchlist service validates users and movies by calling respective services
- Uses httpx for async HTTP requests between services
- Batch endpoint reduces N+1 query problem

### Database Design
Each service has its own PostgreSQL database, with tables defined as SQLModel classes in each service's `db.py`:
- **userdb**: Stores user accounts (passwords stored as bcrypt hashes)
- **moviedb**: Stores movie catalog
- **watchlistdb**: Stores user-movie relationships with indexes on user_id and movie_id

Database and Redis ports are published on `127.0.0.1` only, so they are reachable from the host for tools like PgAdmin but not from the network.

## Project Structure

```
.
├── docker-compose.yml
├── nginx/
│   └── nginx.conf            # API gateway routing + static frontend
├── frontend/                 # Alpine.js + Tailwind single-page UI (no build step)
│   ├── index.html
│   ├── js/api.js
│   ├── js/app.js
│   └── css/styles.css
├── user-service/
│   ├── main.py               # FastAPI routes
│   ├── db.py                 # SQLModel table definition + init
│   ├── test_main.py
│   ├── requirements.txt
│   └── Dockerfile
├── movie-service/
│   ├── main.py
│   ├── db.py
│   ├── test_main.py
│   ├── requirements.txt
│   └── Dockerfile
├── watchlist-service/
│   ├── main.py
│   ├── db.py
│   ├── requirements.txt
│   └── Dockerfile
├── test.http                 # Manual API tests (VS Code REST Client)
├── AWS_DEPLOYMENT_GUIDE.md   # Notes on deploying to EC2 / ECS / EKS
├── CLAUDE.md                 # Claude Code project instructions
└── README.md
```

## Stopping Services

```bash
docker compose down
```

To remove volumes (databases):
```bash
docker compose down -v
```

## Development

### Running Unit Tests
Each service's tests mock the database and cache, so no containers are needed:
```bash
cd movie-service && pip install -r requirements.txt pytest httpx && pytest
cd user-service  && pip install -r requirements.txt pytest httpx && pytest
```

### Viewing Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f user-service
docker compose logs -f movie-service
docker compose logs -f watchlist-service
```

### Accessing Redis CLI
```bash
docker exec -it redis redis-cli

# Check cached movies
KEYS movie:*
GET movie:1
```

### Accessing PostgreSQL
```bash
# User DB
docker exec -it user-db psql -U user -d userdb

# Movie DB
docker exec -it movie-db psql -U movie -d moviedb

# Watchlist DB
docker exec -it watchlist-db psql -U watchlist -d watchlistdb
```

## Technology Stack

- **Framework**: FastAPI (Python)
- **Databases**: PostgreSQL 15
- **Cache**: Redis 7
- **API Gateway**: Nginx
- **Container Orchestration**: Docker Compose
- **HTTP Client**: httpx

## License

MIT. See [LICENSE](LICENSE).
