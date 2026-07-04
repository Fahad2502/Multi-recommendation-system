"""
Recommendation routes.

GET  /health
GET  /movie-details/{movie_id}
POST /recommend
"""
import asyncio
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException

from app.core import cache
from app.schemas import (
    HealthResponse,
    MovieDetailResponse,
    RecommendRequest,
    RecommendResponse,
)
from app.services import books as book_svc
from app.services import music as music_svc
from app.services import tmdb as tmdb_svc

router = APIRouter(tags=["Recommendations"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness check — returns version and current UTC timestamp."""
    return HealthResponse(
        status="ok",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/movie-details/{movie_id}", response_model=MovieDetailResponse)
async def movie_details(movie_id: int) -> MovieDetailResponse:
    """
    Return full details for a TMDB movie ID:
    title, overview, rating, genres, runtime, top-3 cast, YouTube trailer key.
    Results are cached for 1 hour.
    """
    cache_key = f"details_{movie_id}"
    hit = cache.get(cache_key)
    if hit:
        return hit

    async with httpx.AsyncClient() as client:
        try:
            result = await tmdb_svc.get_movie_details(client, movie_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"Movie not found: {exc}")

    cache.set(cache_key, result)
    return result


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(body: RecommendRequest) -> RecommendResponse:
    """
    Core endpoint.  Given a movie title:
    1. Extract genre + keyword context from TMDB
    2. Concurrently fetch similar movies, music, and books
    3. Return structured results with semantic context

    Results are cached for 1 hour.
    """
    movie     = body.movie           # already stripped + validated by Pydantic
    cache_key = f"rec_{movie.lower()}"

    hit = cache.get(cache_key)
    if hit:
        hit["meta"]["cached"] = True
        return hit

    start = datetime.utcnow()
    logger.info("Recommendation request: '%s'", movie)

    async with httpx.AsyncClient() as client:
        ctx = await tmdb_svc.get_movie_context(client, movie)
        logger.info(
            "Context → genres=%s  keywords=%s",
            ctx["genres"], ctx["keywords"][:5],
        )

        movies, music, books = await asyncio.gather(
            tmdb_svc.get_similar_movies(client, ctx),
            music_svc.get_music_recommendations(ctx),
            book_svc.get_book_recommendations(client, ctx),
        )

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(
        "Done in %.2fs → %d movies  %d music  %d books",
        elapsed, len(movies), len(music), len(books),
    )

    response = {
        "movies" : movies,
        "music"  : music,
        "books"  : books,
        "context": {
            "matched_title": ctx["title"],
            "genres"       : ctx["genres"],
            "keywords"     : ctx["keywords"],
        },
        "meta": {
            "query"          : movie,
            "total_results"  : len(movies) + len(music) + len(books),
            "processing_time": f"{elapsed:.2f}s",
            "cached"         : False,
        },
    }
    cache.set(cache_key, response)
    return response
