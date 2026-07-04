"""
Books service — Open Library API.

Four parallel queries (title + genre subjects + keyword subjects) give
semantically related books instead of just searching the movie title.
No API key required. No rate limits.
"""
import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_OL_SEARCH = "https://openlibrary.org/search.json"
_OL_COVER  = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
_COVER_PLACEHOLDER = "https://via.placeholder.com/128x192?text=Book"

# TMDB genre → Open Library subject term
_GENRE_TO_SUBJECT: dict[str, str] = {
    "Science Fiction": "science fiction",
    "Action"         : "action adventure",
    "Thriller"       : "psychological thriller",
    "Horror"         : "horror fiction",
    "Romance"        : "romance",
    "Drama"          : "drama fiction",
    "Comedy"         : "comedy",
    "Fantasy"        : "fantasy fiction",
    "Mystery"        : "mystery detective",
    "Animation"      : "adventure fiction",
    "Crime"          : "crime fiction",
    "History"        : "historical fiction",
    "War"            : "war fiction",
    "Biography"      : "biography memoir",
}

_OL_FIELDS = (
    "key,title,author_name,cover_i,subject,"
    "first_publish_year,ratings_average,first_sentence"
)


async def get_book_recommendations(client: httpx.AsyncClient, ctx: dict) -> list:
    """
    Build 4 queries from title + genres + keywords and fire them concurrently.
    Deduplicate by Open Library work key.
    """
    title    = ctx["title"]
    genres   = ctx["genres"]
    keywords = ctx["keywords"]

    queries = [title]
    queries += [_GENRE_TO_SUBJECT.get(g, g.lower()) for g in genres[:2]]
    if keywords:
        queries.append(" ".join(keywords[:3]))

    # Fire all queries at the same time
    raw_results = await asyncio.gather(*[_fetch(client, q) for q in queries[:4]])

    books: list[dict] = []
    seen: set[str] = set()

    for docs in raw_results:
        for doc in docs:
            key = doc.get("key", "")
            if not key or key in seen:
                continue
            seen.add(key)

            cover_id  = doc.get("cover_i")
            thumbnail = _OL_COVER.format(cover_id=cover_id) if cover_id else _COVER_PLACEHOLDER

            desc = doc.get("first_sentence", [])
            if isinstance(desc, list):
                desc = desc[0] if desc else "No description available."
            desc = str(desc)
            if len(desc) > 200:
                desc = desc[:197] + "..."

            rating = doc.get("ratings_average")

            books.append({
                "title"      : doc.get("title", "No title"),
                "authors"    : doc.get("author_name", ["Unknown Author"]),
                "description": desc,
                "thumbnail"  : thumbnail,
                "rating"     : round(float(rating), 1) if rating else "N/A",
                "genre"      : (doc.get("subject") or ["General"])[0],
                "year"       : doc.get("first_publish_year", "Unknown"),
            })

        if len(books) >= settings.max_books:
            break

    return books[:settings.max_books]


async def _fetch(client: httpx.AsyncClient, query: str) -> list:
    """Single Open Library search call."""
    try:
        r = await client.get(
            _OL_SEARCH,
            params={"q": query, "limit": 5, "fields": _OL_FIELDS},
            timeout=settings.request_timeout,
        )
        r.raise_for_status()
        return r.json().get("docs", [])
    except Exception as exc:
        logger.warning("Open Library query '%s' failed: %s", query, exc)
        return []
