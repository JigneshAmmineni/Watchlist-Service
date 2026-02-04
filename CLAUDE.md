# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Code Style

- Always write a clear and concise comment describing the purpose of a function above the actual function implementation.

## Project Overview

Movie Watchlist Microservices System - a distributed architecture for managing users, movies, and watchlists using FastAPI, PostgreSQL, Redis, and Docker Compose.

## Common Commands

```bash
# Start all services
docker compose up --build

# Start in detached mode
docker compose up -d --build

# Stop all services
docker compose down

# Stop and remove volumes (clears databases)
docker compose down -v

# View logs
docker compose logs -f                    # All services
docker compose logs -f user-service       # Specific service

# Access databases via CLI
docker exec -it user-db psql -U user -d userdb
docker exec -it movie-db psql -U movie -d moviedb
docker exec -it watchlist-db psql -U watchlist -d watchlistdb

# Access Redis CLI
docker exec -it redis redis-cli
```

## Architecture

### Service Communication Flow
```
Client → Nginx API Gateway (port 8080) → Microservices (internal port 8000)
                                              ↓
                                         PostgreSQL (per-service DB)
```

### Services
- **user-service**: User CRUD operations → user-db (PostgreSQL)
- **movie-service**: Movie CRUD with Redis cache-aside pattern → movie-db + Redis
- **watchlist-service**: User-movie relationships, validates users/movies via HTTP calls to other services → watchlist-db

### API Gateway Routing (nginx)
| External Route | Internal Route |
|---------------|----------------|
| `/api/users/*` | `user-service:8000/users/*` |
| `/api/movies/*` | `movie-service:8000/movies/*` |
| `/api/watchlist/*` | `watchlist-service:8000/watchlist/*` |
| `/api/health/{service}` | `{service}:8000/health` |

### Database Ports (for external access via PgAdmin, etc.)
| Database | Host Port | Username | Password | Database Name |
|----------|-----------|----------|----------|---------------|
| user-db | 5432 | user | password | userdb |
| movie-db | 5433 | movie | password | moviedb |
| watchlist-db | 5434 | watchlist | password | watchlistdb |

### Key Patterns
- **Cache-aside (movie-service)**: Check Redis first, fetch from DB on miss, cache result. TTL: 1 hour.
- **Service validation (watchlist-service)**: Uses httpx to validate user/movie existence before creating watchlist entries.
- **Health checks**: All services expose `/health` endpoint. Docker uses Python urllib for health checks (curl not available in slim images).

## Testing

Use `test.http` with VSCode REST Client extension for manual API testing against `http://localhost:8080`.
