// Centralized API module providing fetch wrappers for all microservice endpoints.
const API = {
  // Internal fetch helper that handles JSON parsing and FastAPI error responses.
  async _request(url, options = {}) {
    const config = {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    };
    const response = await fetch(url, config);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed with status ${response.status}`);
    }
    if (response.status === 204) return null;
    return response.json();
  },

  // ── Users ──────────────────────────────────────────────
  getUsers() {
    return this._request('/api/users');
  },
  getUser(id) {
    return this._request(`/api/users/${id}`);
  },
  createUser(data) {
    return this._request('/api/users', { method: 'POST', body: JSON.stringify(data) });
  },
  updateUser(id, data) {
    return this._request(`/api/users/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  deleteUser(id) {
    return this._request(`/api/users/${id}`, { method: 'DELETE' });
  },

  // ── Movies ─────────────────────────────────────────────
  getMovies(genre) {
    const query = genre ? `?genre=${encodeURIComponent(genre)}` : '';
    return this._request(`/api/movies${query}`);
  },
  getMovie(id) {
    return this._request(`/api/movies/${id}`);
  },
  createMovie(data) {
    return this._request('/api/movies', { method: 'POST', body: JSON.stringify(data) });
  },
  updateMovie(id, data) {
    return this._request(`/api/movies/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  deleteMovie(id) {
    return this._request(`/api/movies/${id}`, { method: 'DELETE' });
  },

  // ── Watchlist ──────────────────────────────────────────
  addToWatchlist(userId, movieId) {
    return this._request('/api/watchlist', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, movie_id: movieId }),
    });
  },
  getUserWatchlist(userId) {
    return this._request(`/api/watchlist/user/${userId}`);
  },
  exportWatchlist(userId) {
    return this._request(`/api/watchlist/user/${userId}/export`);
  },
  checkInWatchlist(userId, movieId) {
    return this._request(`/api/watchlist/user/${userId}/movie/${movieId}`);
  },
  removeFromWatchlist(userId, movieId) {
    return this._request(`/api/watchlist/user/${userId}/movie/${movieId}`, { method: 'DELETE' });
  },
  removeWatchlistById(id) {
    return this._request(`/api/watchlist/${id}`, { method: 'DELETE' });
  },
  getMovieWatchers(movieId) {
    return this._request(`/api/watchlist/movie/${movieId}`);
  },

  // ── Health ─────────────────────────────────────────────
  // Checks health of all three services concurrently.
  async checkHealth() {
    const endpoints = {
      users: '/api/health/users',
      movies: '/api/health/movies',
      watchlist: '/api/health/watchlist',
    };
    const results = {};
    const promises = Object.entries(endpoints).map(async ([name, url]) => {
      try {
        await this._request(url);
        results[name] = 'healthy';
      } catch {
        results[name] = 'unhealthy';
      }
    });
    await Promise.allSettled(promises);
    return results;
  },
};
