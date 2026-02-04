// Registers the main Alpine.js component that drives the entire single-page application.
document.addEventListener('alpine:init', () => {
  Alpine.data('watchlistApp', () => ({
    // ── State ──────────────────────────────────────────
    currentTab: 'users',

    // Entity lists
    users: [],
    movies: [],
    watchlist: [],

    // Loading states
    loadingUsers: false,
    loadingMovies: false,
    loadingWatchlist: false,

    // Modal visibility
    showUserModal: false,
    showMovieModal: false,
    showAddToWatchlistModal: false,
    showConfirmModal: false,

    // Form data
    userForm: { name: '', email: '', password: '' },
    movieForm: { title: '', director: '', year: '', genre: '', rating: '' },

    // Edit tracking (null = create mode, object = edit mode)
    editingUser: null,
    editingMovie: null,

    // Movie filtering
    genreFilter: '',
    availableGenres: [],

    // Watchlist
    selectedUserId: '',
    watchlistUsers: [],
    availableMoviesForWatchlist: [],

    // Confirm modal
    confirmMessage: '',
    confirmAction: null,

    // Toast notification
    toast: { show: false, message: '', type: 'success' },
    toastTimeout: null,

    // Health status
    health: { users: 'checking', movies: 'checking', watchlist: 'checking' },

    // ── Lifecycle ────────────────────────────────────────
    async init() {
      this.checkHealth();
      await this.loadUsers();
      // Poll health every 30s
      setInterval(() => this.checkHealth(), 30000);
    },

    // ── Navigation ───────────────────────────────────────
    // Switches the active tab and loads the relevant data.
    async switchTab(tab) {
      this.currentTab = tab;
      if (tab === 'users') await this.loadUsers();
      else if (tab === 'movies') await this.loadMovies();
      else if (tab === 'watchlist') {
        await this.loadUsersForWatchlist();
        if (this.selectedUserId) await this.loadWatchlist();
      }
    },

    // ── Health ───────────────────────────────────────────
    // Fetches the health status of all backend services.
    async checkHealth() {
      this.health = await API.checkHealth();
    },

    // ── Toast ────────────────────────────────────────────
    // Shows a temporary notification at the top-right of the screen.
    showToast(message, type = 'success') {
      if (this.toastTimeout) clearTimeout(this.toastTimeout);
      this.toast = { show: true, message, type };
      this.toastTimeout = setTimeout(() => {
        this.toast.show = false;
      }, 3500);
    },

    // ── Users ────────────────────────────────────────────
    // Loads all users from the backend.
    async loadUsers() {
      this.loadingUsers = true;
      try {
        this.users = await API.getUsers();
      } catch (e) {
        this.showToast(e.message, 'error');
      } finally {
        this.loadingUsers = false;
      }
    },

    // Opens the user modal in create mode with an empty form.
    openCreateUser() {
      this.editingUser = null;
      this.userForm = { name: '', email: '', password: '' };
      this.showUserModal = true;
    },

    // Opens the user modal in edit mode, pre-filling the form with existing data.
    openEditUser(user) {
      this.editingUser = user;
      this.userForm = { name: user.name, email: user.email, password: user.password };
      this.showUserModal = true;
    },

    // Saves (creates or updates) a user based on the current editing state.
    async saveUser() {
      try {
        if (this.editingUser) {
          await API.updateUser(this.editingUser.id, this.userForm);
          this.showToast('User updated successfully');
        } else {
          await API.createUser(this.userForm);
          this.showToast('User created successfully');
        }
        this.showUserModal = false;
        await this.loadUsers();
      } catch (e) {
        this.showToast(e.message, 'error');
      }
    },

    // Shows a confirmation dialog before deleting a user.
    confirmDeleteUser(user) {
      this.confirmMessage = `Delete user "${user.name}"? This cannot be undone.`;
      this.confirmAction = async () => {
        try {
          await API.deleteUser(user.id);
          this.showToast('User deleted successfully');
          await this.loadUsers();
        } catch (e) {
          this.showToast(e.message, 'error');
        }
      };
      this.showConfirmModal = true;
    },

    // ── Movies ───────────────────────────────────────────
    // Loads all movies, optionally filtered by the selected genre.
    async loadMovies() {
      this.loadingMovies = true;
      try {
        const allMovies = await API.getMovies();
        // Build genre list from unfiltered results
        this.availableGenres = [...new Set(allMovies.map(m => m.genre))].sort();

        if (this.genreFilter) {
          this.movies = allMovies.filter(m => m.genre === this.genreFilter);
        } else {
          this.movies = allMovies;
        }
      } catch (e) {
        this.showToast(e.message, 'error');
      } finally {
        this.loadingMovies = false;
      }
    },

    // Opens the movie modal in create mode with an empty form.
    openCreateMovie() {
      this.editingMovie = null;
      this.movieForm = { title: '', director: '', year: '', genre: '', rating: '' };
      this.showMovieModal = true;
    },

    // Opens the movie modal in edit mode, pre-filling the form with existing data.
    openEditMovie(movie) {
      this.editingMovie = movie;
      this.movieForm = {
        title: movie.title,
        director: movie.director,
        year: movie.year,
        genre: movie.genre,
        rating: movie.rating || '',
      };
      this.showMovieModal = true;
    },

    // Saves (creates or updates) a movie based on the current editing state.
    async saveMovie() {
      try {
        const data = {
          ...this.movieForm,
          year: parseInt(this.movieForm.year),
          rating: this.movieForm.rating ? parseFloat(this.movieForm.rating) : null,
        };
        if (this.editingMovie) {
          await API.updateMovie(this.editingMovie.id, data);
          this.showToast('Movie updated successfully');
        } else {
          await API.createMovie(data);
          this.showToast('Movie created successfully');
        }
        this.showMovieModal = false;
        await this.loadMovies();
      } catch (e) {
        this.showToast(e.message, 'error');
      }
    },

    // Shows a confirmation dialog before deleting a movie.
    confirmDeleteMovie(movie) {
      this.confirmMessage = `Delete movie "${movie.title}"? This cannot be undone.`;
      this.confirmAction = async () => {
        try {
          await API.deleteMovie(movie.id);
          this.showToast('Movie deleted successfully');
          await this.loadMovies();
        } catch (e) {
          this.showToast(e.message, 'error');
        }
      };
      this.showConfirmModal = true;
    },

    // Applies the currently selected genre filter and reloads movies.
    async filterByGenre() {
      await this.loadMovies();
    },

    // ── Watchlist ────────────────────────────────────────
    // Loads the user list for the watchlist tab's user selector dropdown.
    async loadUsersForWatchlist() {
      try {
        this.watchlistUsers = await API.getUsers();
        // Auto-select first user if none selected
        if (!this.selectedUserId && this.watchlistUsers.length > 0) {
          this.selectedUserId = this.watchlistUsers[0].id;
          await this.loadWatchlist();
        }
      } catch (e) {
        this.showToast(e.message, 'error');
      }
    },

    // Loads the watchlist entries for the currently selected user.
    async loadWatchlist() {
      if (!this.selectedUserId) return;
      this.loadingWatchlist = true;
      try {
        this.watchlist = await API.getUserWatchlist(this.selectedUserId);
      } catch (e) {
        this.showToast(e.message, 'error');
      } finally {
        this.loadingWatchlist = false;
      }
    },

    // Opens the "add movie to watchlist" picker, filtering out already-added movies.
    async openAddToWatchlist() {
      try {
        const allMovies = await API.getMovies();
        const watchlistMovieIds = this.watchlist.map(w => w.movie_id);
        this.availableMoviesForWatchlist = allMovies.filter(
          m => !watchlistMovieIds.includes(m.id)
        );
        this.showAddToWatchlistModal = true;
      } catch (e) {
        this.showToast(e.message, 'error');
      }
    },

    // Adds a movie to the current user's watchlist.
    async addMovieToWatchlist(movieId) {
      try {
        await API.addToWatchlist(this.selectedUserId, movieId);
        this.showToast('Movie added to watchlist');
        this.showAddToWatchlistModal = false;
        await this.loadWatchlist();
      } catch (e) {
        this.showToast(e.message, 'error');
      }
    },

    // Removes a movie from the current user's watchlist after confirmation.
    confirmRemoveFromWatchlist(entry) {
      this.confirmMessage = `Remove "${entry.movie_title}" from watchlist?`;
      this.confirmAction = async () => {
        try {
          await API.removeFromWatchlist(this.selectedUserId, entry.movie_id);
          this.showToast('Removed from watchlist');
          await this.loadWatchlist();
        } catch (e) {
          this.showToast(e.message, 'error');
        }
      };
      this.showConfirmModal = true;
    },

    // Exports the current user's watchlist as a downloadable JSON file.
    async exportWatchlist() {
      try {
        const data = await API.exportWatchlist(this.selectedUserId);
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `watchlist-user-${this.selectedUserId}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('Watchlist exported');
      } catch (e) {
        this.showToast(e.message, 'error');
      }
    },

    // ── Confirm modal ────────────────────────────────────
    // Executes the stored confirm action and closes the modal.
    async executeConfirm() {
      if (this.confirmAction) await this.confirmAction();
      this.showConfirmModal = false;
      this.confirmAction = null;
    },

    // ── Helpers ──────────────────────────────────────────
    // Returns a color class for the genre badge based on genre name.
    genreColor(genre) {
      const colors = {
        'Action': 'bg-red-100 text-red-700',
        'Sci-Fi': 'bg-blue-100 text-blue-700',
        'Crime': 'bg-yellow-100 text-yellow-700',
        'Drama': 'bg-purple-100 text-purple-700',
        'Comedy': 'bg-green-100 text-green-700',
        'Horror': 'bg-gray-100 text-gray-700',
        'Romance': 'bg-pink-100 text-pink-700',
        'Thriller': 'bg-orange-100 text-orange-700',
      };
      return colors[genre] || 'bg-indigo-100 text-indigo-700';
    },

    // Renders a star rating as a visual string of filled and empty stars.
    renderStars(rating) {
      if (!rating) return '';
      const full = Math.round(rating / 2);
      return '★'.repeat(full) + '☆'.repeat(5 - full);
    },
  }));
});
