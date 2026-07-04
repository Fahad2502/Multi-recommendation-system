"""
TMDB service — all calls to api.themoviedb.org live here.

Public surface:
  get_movie_context(client, movie_name) -> dict
  get_similar_movies(client, ctx)       -> list[MovieCard-dict]
  get_movie_details(client, movie_id)   -> MovieDetailResponse-dict
"""
import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE = settings.tmdb_base_url
_KEY  = settings.movies_api_key


async def _get(client: httpx.AsyncClient, path: str, **params: Any) -> dict:
    """Fire one TMDB GET, injecting api_key and language automatically."""
    params["api_key"] = _KEY
    params["language"] = "en-US"
    response = await client.get(f"{_BASE}{path}", params=params,
                                timeout=settings.request_timeout)
    response.raise_for_status()
    return response.json()


async def get_movie_context(client: httpx.AsyncClient, movie_name: str) -> dict:
    """
    Search TMDB for movie_name, pick the most popular hit, then fetch
    genres, thematic keywords, and credits in parallel.

    Returns a context dict used by all three recommendation services.
    """
    search = await _get(client, "/search/movie", query=movie_name)
    results = search.get("results", [])

    if not results:
        return {
            "movie_id": None, "title": movie_name,
            "genres": [], "keywords": [], "cast_names": [], "director": None,
            "overview": "", "tmdb_rating": 0,
        }

    results.sort(key=lambda m: m.get("popularity", 0), reverse=True)
    movie_id = results[0]["id"]

    details, keywords_data, credits = await asyncio.gather(
        _get(client, f"/movie/{movie_id}"),
        _get(client, f"/movie/{movie_id}/keywords"),
        _get(client, f"/movie/{movie_id}/credits"),
    )

    return {
        "movie_id"   : movie_id,
        "title"      : details.get("title", movie_name),
        "genres"     : [g["name"] for g in details.get("genres", [])],
        "keywords"   : [k["name"] for k in keywords_data.get("keywords", [])][:10],
        "cast_names" : [c["name"] for c in credits.get("cast", [])][:5],
        "director"   : next(
            (c["name"] for c in credits.get("crew", []) if c["job"] == "Director"), None
        ),
        "overview"   : details.get("overview", ""),
        "tmdb_rating": details.get("vote_average", 0),
    }


async def get_similar_movies(client: httpx.AsyncClient, ctx: dict) -> list:
    """
    Use TMDB's collaborative-filter (/recommendations) and content-based
    (/similar) engines. Falls back to genre discovery if results are sparse.
    """
    movie_id = ctx["movie_id"]
    if not movie_id:
        return []

    similar, reco = await asyncio.gather(
        _get(client, f"/movie/{movie_id}/similar"),
        _get(client, f"/movie/{movie_id}/recommendations"),
    )

    seen: set[int] = set()
    movies: list[dict] = []

    def _add(m: dict) -> None:
        if m["id"] not in seen and m.get("poster_path"):
            seen.add(m["id"])
            movies.append({
                "id"          : m["id"],
                "title"       : m["title"],
                "poster"      : f"https://image.tmdb.org/t/p/w500{m['poster_path']}",
                "release_date": m.get("release_date", ""),
                "rating"      : round(m.get("vote_average", 0), 1),
                "overview"    : (m.get("overview", "")[:150] + "...") if m.get("overview") else "",
            })

    for m in reco.get("results", [])[:5]:
        _add(m)
    for m in similar.get("results", [])[:5]:
        _add(m)

    # Backfill via genre discovery when results are thin
    if len(movies) < 4 and ctx["genres"]:
        genre_list = await _get(client, "/genre/movie/list")
        genre_id = next(
            (g["id"] for g in genre_list.get("genres", []) if g["name"] in ctx["genres"]),
            None,
        )
        if genre_id:
            discovered = await _get(
                client, "/discover/movie",
                with_genres=genre_id,
                sort_by="vote_average.desc",
                vote_count_gte=500,
            )
            for m in discovered.get("results", [])[:6]:
                _add(m)

    return movies[:settings.max_movies]


async def get_movie_details(client: httpx.AsyncClient, movie_id: int) -> dict:
    """Fetch title, overview, cast (top 3), and YouTube trailer key."""
    details, credits, videos = await asyncio.gather(
        _get(client, f"/movie/{movie_id}"),
        _get(client, f"/movie/{movie_id}/credits"),
        _get(client, f"/movie/{movie_id}/videos"),
    )

    cast = [
        {
            "name"   : a["name"],
            "profile": (
                f"https://image.tmdb.org/t/p/w185{a['profile_path']}"
                if a.get("profile_path")
                else "https://via.placeholder.com/80"
            ),
        }
        for a in credits.get("cast", [])[:3]
    ]

    trailer = next(
        (v["key"] for v in videos.get("results", [])
         if v.get("type") == "Trailer" and v.get("site") == "YouTube"),
        None,
    )

    return {
        "title"   : details.get("title"),
        "overview": details.get("overview"),
        "rating"  : details.get("vote_average"),
        "release" : details.get("release_date"),
        "genres"  : [g["name"] for g in details.get("genres", [])],
        "runtime" : details.get("runtime"),
        "cast"    : cast,
        "trailer" : trailer,
    }
