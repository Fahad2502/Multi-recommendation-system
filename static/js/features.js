/**
 * RecoHub Additional Features
 */

class AdvancedFeatures {
    constructor() {
        this.favorites = this.loadFavorites();
        this.searchHistory = this.loadSearchHistory();
        this.init();
    }

    init() {
        this.setupKeyboardShortcuts();
        this.setupShareFeature();
        this.setupFavorites();
    }

    // Keyboard shortcuts
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('searchInput').focus();
            }
            
            // Escape to clear search
            if (e.key === 'Escape') {
                document.getElementById('searchInput').value = '';
                document.getElementById('resultsContainer').style.display = 'none';
            }
        });
    }

    // Share functionality
    setupShareFeature() {
        // Add share buttons to results
        this.addShareButtons();
    }

    addShareButtons() {
        // This would add share buttons to each recommendation card
        // Implementation would depend on the specific sharing requirements
    }

    // Favorites system
    setupFavorites() {
        // Add favorite buttons to movie cards
        // This would require modifying the movie card HTML
    }

    addToFavorites(item, type) {
        const favoriteItem = {
            id: item.id,
            title: item.title,
            type: type,
            addedAt: Date.now()
        };

        this.favorites.push(favoriteItem);
        this.saveFavorites();
        this.showNotification(`Added "${item.title}" to favorites!`, 'success');
    }

    removeFromFavorites(itemId) {
        this.favorites = this.favorites.filter(item => item.id !== itemId);
        this.saveFavorites();
    }

    loadFavorites() {
        try {
            return JSON.parse(localStorage.getItem('recohub_favorites') || '[]');
        } catch {
            return [];
        }
    }

    saveFavorites() {
        localStorage.setItem('recohub_favorites', JSON.stringify(this.favorites));
    }

    // Search history
    addToSearchHistory(query) {
        const historyItem = {
            query,
            timestamp: Date.now()
        };

        // Remove duplicates and add to beginning
        this.searchHistory = this.searchHistory.filter(item => item.query !== query);
        this.searchHistory.unshift(historyItem);

        // Keep only last 10 searches
        this.searchHistory = this.searchHistory.slice(0, 10);
        this.saveSearchHistory();
    }

    loadSearchHistory() {
        try {
            return JSON.parse(localStorage.getItem('recohub_search_history') || '[]');
        } catch {
            return [];
        }
    }

    saveSearchHistory() {
        localStorage.setItem('recohub_search_history', JSON.stringify(this.searchHistory));
    }

    // Export functionality
    exportRecommendations(data, format = 'json') {
        const exportData = {
            query: data.meta?.query,
            timestamp: new Date().toISOString(),
            recommendations: {
                movies: data.movies,
                music: data.music,
                books: data.books
            }
        };

        if (format === 'json') {
            this.downloadJSON(exportData, `recohub-recommendations-${Date.now()}.json`);
        } else if (format === 'csv') {
            this.downloadCSV(exportData, `recohub-recommendations-${Date.now()}.csv`);
        }
    }

    downloadJSON(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        this.downloadBlob(blob, filename);
    }

    downloadCSV(data, filename) {
        // Convert recommendations to CSV format
        let csv = 'Type,Title,Rating,Description\n';
        
        data.recommendations.movies.forEach(movie => {
            csv += `Movie,"${movie.title}",${movie.rating},"${movie.overview}"\n`;
        });
        
        data.recommendations.music.forEach(track => {
            csv += `Music,"${track.title} by ${track.artist}",${track.rating},"${track.description}"\n`;
        });
        
        data.recommendations.books.forEach(book => {
            csv += `Book,"${book.title}",${book.rating},"${book.description}"\n`;
        });

        const blob = new Blob([csv], { type: 'text/csv' });
        this.downloadBlob(blob, filename);
    }

    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    showNotification(message, type = 'info') {
        // Use the existing notification system from main.js
        if (window.recoAI) {
            window.recoAI.showNotification(message, type);
        }
    }
}

// Initialize advanced features
window.advancedFeatures = new AdvancedFeatures();