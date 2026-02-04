# Frontend Changes

## Overview
Added a single-page web UI for the Movie Watchlist system, served through the existing nginx API gateway. Uses Alpine.js for reactivity and Tailwind CSS for styling, both loaded via CDN — no build step required.

## New Files

### `frontend/index.html`
Main SPA with three tabbed views (Users, Movies, Watchlist). Includes:
- Health status bar showing live service status with pulsing indicators
- Users tab: table with create/edit/delete via modal forms
- Movies tab: card grid with genre filtering, star ratings, genre badges, and CRUD modals
- Watchlist tab: user selector dropdown, enriched watchlist table, add-movie picker, JSON export
- Confirm-delete dialog and toast notifications
- Dark glassmorphism theme with gradient background

### `frontend/js/api.js`
Centralized API module (`API` global object) with fetch wrappers for all endpoints:
- Users: `getUsers`, `getUser`, `createUser`, `updateUser`, `deleteUser`
- Movies: `getMovies` (with genre filter), `getMovie`, `createMovie`, `updateMovie`, `deleteMovie`
- Watchlist: `addToWatchlist`, `getUserWatchlist`, `exportWatchlist`, `checkInWatchlist`, `removeFromWatchlist`, `removeWatchlistById`, `getMovieWatchers`
- Health: `checkHealth` — concurrent health check of all three services

### `frontend/js/app.js`
Alpine.js component (`watchlistApp`) registered via `alpine:init`. Manages:
- Tab navigation and data loading
- CRUD operations for users and movies with modal forms
- Watchlist management: user selection, add/remove movies, JSON export download
- Toast notifications, confirm dialogs, loading spinners
- Genre color mapping and star-rating rendering helpers

### `frontend/css/styles.css`
Custom CSS for effects Tailwind can't handle inline:
- Toast slide-in/slide-out animations
- Loading spinner keyframes
- Glassmorphism card styles with backdrop blur
- Health dot pulse animations
- Tab underline transitions
- Movie card staggered entrance animations
- Star rating gradient text
- Custom scrollbar styling
- Dark gradient background

## Modified Files

### `nginx/nginx.conf`
- Added `include /etc/nginx/mime.types;` and `default_type application/octet-stream;` in the `http` block so JS/CSS files are served with correct MIME types
- Added `root /usr/share/nginx/html;` and `index index.html;` in the `server` block
- Replaced the root `location /` JSON response with `try_files $uri $uri/ /index.html;` for SPA fallback
- All `/api/*` proxy routes remain unchanged

### `docker-compose.yml`
- Added volume mount `./frontend:/usr/share/nginx/html:ro` to the `api-gateway` service to serve static frontend files

## How to Test
1. Run `docker compose up --build`
2. Open `http://localhost:8080` in your browser
3. Verify all three service health dots show green
4. Test Users tab: create, edit, and delete a user
5. Test Movies tab: create movies with different genres, use genre filter, edit, delete
6. Test Watchlist tab: select a user, add movies, export JSON, remove movies
7. Verify API still works: `curl http://localhost:8080/api/health/users`
