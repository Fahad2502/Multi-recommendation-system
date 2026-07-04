// Professional RecoAI JavaScript with Authentication

class RecoAI {
    constructor() {
        this.isLoading = false;
        this.currentQuery = '';
        this.user = null;
        this.token = null;
        this.init();
    }

    init() {
        // Check authentication status
        this.checkAuth();
        
        // Add enter key support for search
        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.getRecommendations();
            }
        });

        // Add some initial animations
        this.animateOnLoad();
    }

    // Authentication methods
    checkAuth() {
        this.token = localStorage.getItem('recohub_token');
        const userData = localStorage.getItem('recohub_user');
        
        if (this.token && userData) {
            try {
                this.user = JSON.parse(userData);
                this.showUserMenu();
                this.verifyToken();
            } catch (e) {
                this.logout();
            }
        } else {
            this.showAuthButtons();
        }
    }

    async verifyToken() {
        if (!this.token) return;
        
        try {
            const response = await fetch('/auth/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: this.token })
            });
            
            const data = await response.json();
            
            if (!data.valid) {
                this.logout();
            } else {
                this.user = data.user;
                localStorage.setItem('recohub_user', JSON.stringify(this.user));
            }
        } catch (error) {
            console.error('Token verification failed:', error);
            this.logout();
        }
    }

    showUserMenu() {
        document.getElementById('authButtons').style.display = 'none';
        document.getElementById('userMenu').style.display = 'block';
        document.getElementById('usernameDisplay').textContent = this.user.username;
    }

    showAuthButtons() {
        document.getElementById('userMenu').style.display = 'none';
        document.getElementById('authButtons').style.display = 'block';
    }

    logout() {
        localStorage.removeItem('recohub_token');
        localStorage.removeItem('recohub_user');
        this.token = null;
        this.user = null;
        this.showAuthButtons();
        this.showNotification('Signed out successfully', 'success');
    }

    // Add to favorites
    async addToFavorites(item, type) {
        if (!this.token) {
            this.showNotification('Please sign in to add favorites', 'warning');
            return;
        }

        try {
            const response = await fetch('/user/favorites', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.token}`
                },
                body: JSON.stringify({
                    id: item.id,
                    title: item.title,
                    type: type,
                    poster: item.poster,
                    rating: item.rating
                })
            });

            const data = await response.json();
            
            if (data.success) {
                this.showNotification(`Added "${item.title}" to favorites!`, 'success');
            } else {
                this.showNotification(data.message || 'Already in favorites', 'info');
            }
        } catch (error) {
            this.showNotification('Failed to add to favorites', 'error');
        }
    }

    // Track search in user history
    async trackUserSearch(query) {
        if (!this.token) return;

        try {
            // This would be implemented in the backend
            // For now, we'll just track it locally
            if (window.analytics) {
                window.analytics.trackSearch(query, { user: this.user.username });
            }
        } catch (error) {
            console.error('Failed to track search:', error);
        }
    }

    animateOnLoad() {
        // Stagger animation for elements
        const elements = document.querySelectorAll('.hero-title, .hero-subtitle, .search-container');
        elements.forEach((el, index) => {
            el.style.animationDelay = `${index * 0.2}s`;
        });
    }

    showLoading() {
        this.isLoading = true;
        document.getElementById('loadingOverlay').style.display = 'flex';
        document.body.style.overflow = 'hidden';
        
        // Animate loading steps
        this.animateLoadingSteps();
    }

    animateLoadingSteps() {
        const steps = ['step1', 'step2', 'step3'];
        let currentStep = 0;
        
        const showNextStep = () => {
            if (currentStep < steps.length) {
                document.getElementById(steps[currentStep]).classList.add('active');
                currentStep++;
                setTimeout(showNextStep, 800);
            }
        };
        
        // Reset all steps
        steps.forEach(step => {
            document.getElementById(step).classList.remove('active');
        });
        
        setTimeout(showNextStep, 500);
    }

    hideLoading() {
        this.isLoading = false;
        document.getElementById('loadingOverlay').style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    showResults() {
        const resultsContainer = document.getElementById('resultsContainer');
        resultsContainer.style.display = 'block';
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    updateSectionCount(sectionId, count) {
        document.getElementById(sectionId).textContent = count;
        
        // Update stats bar
        if (sectionId === 'movieCount') {
            this.animateNumber('totalMovies', count);
        } else if (sectionId === 'musicCount') {
            this.animateNumber('totalMusic', count);
        } else if (sectionId === 'bookCount') {
            this.animateNumber('totalBooks', count);
        }
    }

    animateNumber(elementId, targetNumber) {
        const element = document.getElementById(elementId);
        const startNumber = 0;
        const duration = 1000;
        const startTime = performance.now();

        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const currentNumber = Math.floor(startNumber + (targetNumber - startNumber) * progress);
            
            element.textContent = currentNumber;
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    quickSearch(movieTitle) {
        document.getElementById('searchInput').value = movieTitle;
        this.getRecommendations();
    }

    createMovieCard(movie, index) {
        const favoriteBtn = this.token ? 
            `<button class="btn-favorite" onclick="recoAI.addToFavorites({id: ${movie.id}, title: '${movie.title.replace(/'/g, "\\'")}', poster: '${movie.poster}', rating: ${movie.rating}}, 'movie')" title="Add to favorites">
                <i class="fas fa-heart"></i>
            </button>` : '';
            
        return `
            <div class="col-lg-4 col-md-6 col-sm-12">
                <div class="recommendation-card fade-in-up" 
                     style="animation-delay: ${index * 0.1}s"
                     onclick="recoAI.showMovieDetails(${movie.id})">
                    ${favoriteBtn}
                    <img src="${movie.poster || 'https://via.placeholder.com/300x450?text=No+Image'}" 
                         class="card-image" 
                         alt="${movie.title}"
                         onerror="this.src='https://via.placeholder.com/300x450?text=No+Image'">
                    <div class="card-content">
                        <h3 class="card-title">${movie.title}</h3>
                        <p class="card-subtitle">
                            <i class="fas fa-star text-warning"></i> ${movie.rating}/10
                        </p>
                        <p class="card-subtitle">
                            <i class="fas fa-play-circle"></i> Click to view details
                        </p>
                    </div>
                </div>
            </div>
        `;
    }

    createMusicCard(track, index) {
        const rating = Math.round(track.rating * 2) / 2;
        const stars = this.generateStars(rating);
        const previewBtn = track.preview_url
            ? `<a href="${track.preview_url}" target="_blank" class="btn-preview" title="Preview">
                 <i class="fas fa-play-circle"></i> Preview
               </a>`
            : '';
        const linkUrl  = track.spotify_url || '#';
        const linkIcon = track.source === 'itunes' ? 'fa-apple' : 'fa-spotify';
        const linkLabel= track.source === 'itunes' ? 'Apple Music' : 'Spotify';

        return `
            <div class="col-lg-4 col-md-6 col-sm-12">
                <div class="recommendation-card music-card fade-in-up"
                     style="animation-delay: ${index * 0.1}s">
                    <img src="${track.image || 'https://via.placeholder.com/300x300?text=Music'}"
                         class="card-image"
                         alt="${track.artist}"
                         onerror="this.src='https://via.placeholder.com/300x300?text=Music'">
                    <div class="card-content">
                        <h3 class="card-title">${track.title}</h3>
                        <p class="card-subtitle"><i class="fas fa-user"></i> ${track.artist}</p>
                        ${track.album ? `<p class="card-subtitle"><i class="fas fa-record-vinyl"></i> ${track.album}</p>` : ''}
                        <div class="d-flex align-items-center gap-2 mt-2">
                            <span class="rating-stars">${stars}</span>
                            <span class="rating-text">${rating}/5</span>
                        </div>
                        <div class="d-flex gap-2 mt-2">
                            ${previewBtn}
                            ${linkUrl !== '#' ? `<a href="${linkUrl}" target="_blank" class="btn-preview" title="${linkLabel}">
                                <i class="fab ${linkIcon}"></i> ${linkLabel}
                            </a>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    createBookCard(book, index) {
        const authors = Array.isArray(book.authors) ? book.authors.join(', ') : book.authors || 'Unknown Author';
        const rating = book.rating !== 'N/A' ? book.rating : 0;
        const stars = this.generateStars(rating);
        
        return `
            <div class="col-lg-4 col-md-6 col-sm-12">
                <div class="recommendation-card book-card fade-in-up" 
                     style="animation-delay: ${index * 0.1}s">
                    <img src="${book.thumbnail || 'https://via.placeholder.com/300x400?text=Book'}" 
                         class="card-image" 
                         alt="${book.title}"
                         onerror="this.src='https://via.placeholder.com/300x400?text=Book'">
                    <div class="card-content">
                        <h3 class="card-title">${book.title}</h3>
                        <p class="card-subtitle">
                            <i class="fas fa-pen"></i> ${authors}
                        </p>
                        <p class="card-subtitle">
                            <i class="fas fa-tag"></i> ${book.genre || 'General'}
                        </p>
                        ${rating > 0 ? `
                        <div class="card-rating">
                            <span class="rating-stars">${stars}</span>
                            <span class="rating-text">${rating}/5</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    generateStars(rating) {
        const fullStars = Math.floor(rating);
        const hasHalfStar = rating % 1 >= 0.5;
        const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);
        
        return '★'.repeat(fullStars) + 
               (hasHalfStar ? '☆' : '') + 
               '☆'.repeat(emptyStars);
    }

    createEmptyState(type, icon) {
        return `
            <div class="col-12">
                <div class="empty-state">
                    <i class="fas fa-${icon}"></i>
                    <h4>No ${type} found</h4>
                    <p>Try searching for a different movie title</p>
                </div>
            </div>
        `;
    }

    async getRecommendations() {
        const query = document.getElementById('searchInput').value.trim();
        
        if (!query) {
            this.showNotification('Please enter a movie title', 'warning');
            return;
        }

        if (this.isLoading) return;

        this.currentQuery = query;
        this.showLoading();

        try {
            const response = await fetch('/recommend', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movie: query })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Recommendations received:', data);

            this.renderResults(data);
            this.showResults();
            
        } catch (error) {
            console.error('Error fetching recommendations:', error);
            this.showNotification('Failed to fetch recommendations. Please try again.', 'error');
        } finally {
            this.hideLoading();
        }
    }

    renderResults(data) {
        // Show context banner if we have genre/keyword context
        this.renderContextBanner(data.context);

        // Render Movies
        const movieList = document.getElementById('movieList');
        if (data.movies && data.movies.length > 0) {
            movieList.innerHTML = data.movies.map((movie, index) =>
                this.createMovieCard(movie, index)
            ).join('');
            this.updateSectionCount('movieCount', data.movies.length);
        } else {
            movieList.innerHTML = this.createEmptyState('movies', 'film');
            this.updateSectionCount('movieCount', 0);
        }

        // Render Music
        const musicList = document.getElementById('musicList');
        if (data.music && data.music.length > 0) {
            musicList.innerHTML = data.music.map((track, index) =>
                this.createMusicCard(track, index)
            ).join('');
            this.updateSectionCount('musicCount', data.music.length);
        } else {
            musicList.innerHTML = this.createEmptyState('music tracks', 'music');
            this.updateSectionCount('musicCount', 0);
        }

        // Render Books
        const bookList = document.getElementById('bookList');
        if (data.books && data.books.length > 0) {
            bookList.innerHTML = data.books.map((book, index) =>
                this.createBookCard(book, index)
            ).join('');
            this.updateSectionCount('bookCount', data.books.length);
        } else {
            bookList.innerHTML = this.createEmptyState('books', 'book');
            this.updateSectionCount('bookCount', 0);
        }

        // Show processing info
        if (data.meta) {
            console.log(`Recommendations: ${data.meta.total_results} results in ${data.meta.processing_time}`);
        }
    }

    renderContextBanner(context) {
        // Remove old banner
        const old = document.getElementById('contextBanner');
        if (old) old.remove();
        if (!context || !context.genres || context.genres.length === 0) return;

        const genres   = context.genres.map(g => `<span class="suggestion-tag" style="cursor:default">${g}</span>`).join('');
        const keywords = (context.keywords || []).slice(0, 5)
            .map(k => `<span class="suggestion-tag" style="cursor:default;opacity:.7">${k}</span>`).join('');

        const banner = document.createElement('div');
        banner.id = 'contextBanner';
        banner.style.cssText = 'padding:1rem 0 .5rem; animation: fadeInUp .5s ease-out;';
        banner.innerHTML = `
            <p class="text-muted mb-1" style="font-size:.85rem;">
                <i class="fas fa-magic" style="color:#667eea"></i>
                Matched <strong style="color:#fff">${context.matched_title || ''}</strong>
                — recommendations based on:
            </p>
            <div class="suggestion-tags">${genres}${keywords}</div>
        `;

        const statsBar = document.querySelector('.stats-bar');
        if (statsBar) statsBar.parentNode.insertBefore(banner, statsBar);
    }

    async showMovieDetails(movieId) {
        console.log('Showing details for movie ID:', movieId);
        
        const modalBody = document.getElementById('movieDetailContent');
        modalBody.innerHTML = `
            <div class="text-center p-4">
                <div class="loading-spinner mx-auto mb-3"></div>
                <h5>Loading movie details...</h5>
                <p class="text-muted">Fetching cast, reviews, and trailer...</p>
            </div>
        `;
        
        const modal = new bootstrap.Modal(document.getElementById('movieDetailModal'));
        modal.show();

        try {
            const response = await fetch(`/movie-details/${movieId}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Movie details received:', data);

            this.renderMovieDetails(data);
            
        } catch (error) {
            console.error('Error fetching movie details:', error);
            modalBody.innerHTML = `
                <div class="text-center p-4">
                    <i class="fas fa-exclamation-triangle text-warning" style="font-size: 3rem;"></i>
                    <h5 class="mt-3">Failed to load details</h5>
                    <p class="text-muted">Please try again later</p>
                </div>
            `;
        }
    }

    renderMovieDetails(data) {
        const modalBody = document.getElementById('movieDetailContent');
        
        // Build cast HTML
        const castHtml = (data.cast || []).map(actor => `
            <div class="cast-member">
                <img src="${actor.profile}" class="cast-photo" alt="${actor.name}"
                     onerror="this.src='https://via.placeholder.com/80x80?text=Actor'">
                <div class="cast-name">${actor.name}</div>
            </div>
        `).join('');

        // Build trailer HTML
        const trailerHtml = data.trailer
            ? `<div class="ratio ratio-16x9 mb-4">
                 <iframe src="https://www.youtube.com/embed/${data.trailer}" 
                         frameborder="0" allowfullscreen></iframe>
               </div>`
            : `<div class="text-center p-4 bg-secondary bg-opacity-25 rounded">
                 <i class="fas fa-video-slash text-muted" style="font-size: 2rem;"></i>
                 <p class="text-muted mt-2 mb-0">No trailer available</p>
               </div>`;

        // Generate rating stars
        const rating = data.rating || 0;
        const stars = this.generateStars(rating / 2); // Convert 10-point to 5-point scale

        modalBody.innerHTML = `
            <div class="movie-details">
                <div class="row mb-4">
                    <div class="col-12">
                        <h3 class="text-white mb-3">${data.title || "Unknown Title"}</h3>
                        <div class="d-flex align-items-center mb-3">
                            <span class="rating-stars me-2" style="color: #ffd700; font-size: 1.2rem;">${stars}</span>
                            <span class="text-white me-3">${rating}/10</span>
                            <span class="badge bg-primary">${data.release || "Unknown"}</span>
                        </div>
                        <p class="text-light">${data.overview || "No description available."}</p>
                    </div>
                </div>
                
                <div class="mb-4">
                    <h5 class="text-white mb-3">
                        <i class="fas fa-play-circle me-2"></i>Trailer
                    </h5>
                    ${trailerHtml}
                </div>
                
                ${castHtml ? `
                <div class="mb-4">
                    <h5 class="text-white mb-3">
                        <i class="fas fa-users me-2"></i>Cast
                    </h5>
                    <div class="d-flex flex-wrap">
                        ${castHtml}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    }

    showNotification(message, type = 'info') {
        // Create a toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed`;
        toast.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 10000;
            min-width: 300px;
            animation: slideInRight 0.3s ease-out;
        `;
        toast.innerHTML = `
            <i class="fas fa-${type === 'error' ? 'exclamation-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
            ${message}
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-in';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Initialize the application
const recoAI = new RecoAI();

// Global functions for backward compatibility
window.getRecommendations = () => recoAI.getRecommendations();
window.showMovieDetails = (movieId) => recoAI.showMovieDetails(movieId);
window.quickSearch = (movieTitle) => recoAI.quickSearch(movieTitle);

// Global functions for user menu
window.showProfile = () => {
    alert('Profile feature coming soon!');
};

window.showFavorites = () => {
    alert('Favorites feature coming soon!');
};

window.showHistory = () => {
    alert('Search history feature coming soon!');
};

window.logout = () => {
    recoAI.logout();
};

// Add custom animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);