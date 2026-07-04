# RecoHub API Documentation

## Overview
RecoHub provides a RESTful API for cross-domain recommendations across movies, music, and books.

## Base URL
```
http://localhost:5000/api
```

## Endpoints

### GET /health
Health check endpoint to verify service status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-26T20:00:00.000Z",
  "version": "1.0.0"
}
```

### POST /recommend
Get cross-domain recommendations based on a movie title.

**Request Body:**
```json
{
  "movie": "Inception"
}
```

**Response:**
```json
{
  "movies": [...],
  "music": [...],
  "books": [...],
  "meta": {
    "query": "Inception",
    "total_results": 18,
    "processing_time": "1.23s",
    "timestamp": "2026-01-26T20:00:00.000Z",
    "cached": false
  }
}
```

### GET /movie-details/{movie_id}
Get detailed information about a specific movie.

**Parameters:**
- `movie_id` (integer): TMDB movie ID

**Response:**
```json
{
  "title": "Inception",
  "overview": "A thief who steals corporate secrets...",
  "rating": 8.8,
  "release": "2010-07-16",
  "cast": [...],
  "trailer": "YoHD9XEInc0",
  "genres": ["Action", "Science Fiction", "Thriller"],
  "runtime": 148,
  "budget": 160000000,
  "revenue": 836836967
}
```

### GET /stats
Get application statistics and metrics.

**Response:**
```json
{
  "total_requests": "1000+",
  "uptime": "99.9%",
  "avg_response_time": "1.2s",
  "supported_apis": ["TMDB", "Spotify", "Google Books"],
  "version": "1.0.0"
}
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "error": "Error type",
  "message": "Detailed error message"
}
```

## Rate Limits
- TMDB API: 1000 requests per day
- Spotify API: 100 requests per hour
- Google Books API: No limits

## Caching
Responses are cached for 1 hour to improve performance and reduce API usage.