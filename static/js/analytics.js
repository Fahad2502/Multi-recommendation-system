/**
 * RecoHub Analytics - Track user interactions
 */

class Analytics {
    constructor() {
        this.sessionId = this.generateSessionId();
        this.events = [];
        this.startTime = Date.now();
    }

    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    track(event, data = {}) {
        const eventData = {
            event,
            data,
            timestamp: Date.now(),
            sessionId: this.sessionId,
            url: window.location.href,
            userAgent: navigator.userAgent
        };

        this.events.push(eventData);
        console.log('Analytics:', eventData);

        // In a real application, you would send this to your analytics service
        // this.sendToAnalytics(eventData);
    }

    trackSearch(query, results) {
        this.track('search', {
            query,
            totalResults: results.movies.length + results.music.length + results.books.length,
            movieCount: results.movies.length,
            musicCount: results.music.length,
            bookCount: results.books.length,
            processingTime: results.meta?.processing_time
        });
    }

    trackMovieClick(movieId, movieTitle) {
        this.track('movie_click', {
            movieId,
            movieTitle
        });
    }

    trackPageView() {
        this.track('page_view', {
            page: 'home',
            referrer: document.referrer
        });
    }

    trackError(error, context) {
        this.track('error', {
            error: error.message,
            stack: error.stack,
            context
        });
    }

    getSessionStats() {
        return {
            sessionId: this.sessionId,
            duration: Date.now() - this.startTime,
            eventCount: this.events.length,
            events: this.events
        };
    }
}

// Global analytics instance
window.analytics = new Analytics();

// Track page view on load
document.addEventListener('DOMContentLoaded', () => {
    window.analytics.trackPageView();
});