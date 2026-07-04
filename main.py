"""
RecoHub - FastAPI Backend
Smart Cross-Domain Recommendation System
"""
import asyncio
import logging
import os
from datetime import datetime

import httpx
import spotipy
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── API credentials ────────────────────────────────────────────────────────────
MOVIES_API_KEY      = os.getenv("MOVIES_API_KEY",      "d071e08228154bfc3226692bdbd5318e")
SPOTIFY_CLIENT_ID   = os.getenv("SPOTIFY_CLIENT_ID",   "49f4ca2258414e498596139510cce326")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "3ffe2874c6484a7aa6180d3b2e818d07")
TMDB_BASE           = "https://api.themoviedb.org/3"

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RecoHub API",
    description="Smart cross-domain recommendations – Movies, Music & Books",
    version="2.0.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── Pydantic schemas ───────────────────────────────────────────────────────────
class RecommendRequest(BaseModel):
    movie: str

# ── In-memory cache ────────────────────────────────────────────────────────────
_cache: dict = {}

def cache_get(key: str):
    entry = _cache.get(key)
    if entry and (datetime.now() - entry["ts"]).seconds < 3600:
        return entry["data"]
    return None

def cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": datetime.now()}

# ── TMDB helpers ───────────────────────────────────────────────────────────────
async def tmdb_get(client: httpx.AsyncClient, path: str, **params):
    """Single TMDB call with api_key injected."""
    params["api_key"] = MOVIES_API_KEY
    params["language"] = "en-US"
    r = await client.get(f"{TMDB_BASE}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


async def get_movie_context(client: httpx.AsyncClient, movie_name: str) -> dict:
    """
    Find the best-matching movie on TMDB, then pull its genres, keywords,
    and cast so we can power smarter cross-domain recommendations.
    Returns a context dict instead of raw results.
    """
    search = await tmdb_get(client, "/search/movie", query=movie_name)
    results = search.get("results", [])
    if not results:
        return {"movie_id": None, "genres": [], "keywords": [], "cast_names": [], "title": movie_name}

    # Pick the most popular hit
    results.sort(key=lambda m: m.get("popularity", 0), reverse=True)
    top = results[0]
    movie_id = top["id"]

    # Fetch genres + keywords + credits in parallel
    details_task  = tmdb_get(client, f"/movie/{movie_id}")
    keywords_task = tmdb_get(client, f"/movie/{movie_id}/keywords")
    credits_task  = tmdb_get(client, f"/movie/{movie_id}/credits")

    details, keywords_data, credits = await asyncio.gather(
        details_task, keywords_task, credits_task
    )

    genres       = [g["name"] for g in details.get("genres", [])]
    keywords     = [k["name"] for k in keywords_data.get("keywords", [])][:10]
    cast_names   = [c["name"] for c in credits.get("cast", [])][:5]
    director     = next(
        (c["name"] for c in credits.get("crew", []) if c["job"] == "Director"), None
    )

    return {
        "movie_id"   : movie_id,
        "title"      : details.get("title", movie_name),
        "genres"     : genres,
        "keywords"   : keywords,
        "cast_names" : cast_names,
        "director"   : director,
        "overview"   : details.get("overview", ""),
        "tmdb_rating": details.get("vote_average", 0),
    }


async def get_similar_movies(client: httpx.AsyncClient, ctx: dict) -> list:
    """
    Use TMDB's /similar and /recommendations endpoints on the matched movie,
    then fall back to genre-based discovery.  Returns richer results than
    a plain search.
    """
    movie_id = ctx["movie_id"]
    if not movie_id:
        return []

    similar_task  = tmdb_get(client, f"/movie/{movie_id}/similar")
    reco_task     = tmdb_get(client, f"/movie/{movie_id}/recommendations")
    similar, reco = await asyncio.gather(similar_task, reco_task)

    seen, movies = set(), []

    def add_movie(m):
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
        add_movie(m)
    for m in similar.get("results", [])[:5]:
        add_movie(m)

    # If not enough, backfill with a genre-based discover call
    if len(movies) < 4 and ctx["genres"]:
        genre_map = await tmdb_get(client, "/genre/movie/list")
        genre_id = next(
            (g["id"] for g in genre_map.get("genres", []) if g["name"] in ctx["genres"]),
            None,
        )
        if genre_id:
            discover = await tmdb_get(
                client, "/discover/movie",
                with_genres=genre_id,
                sort_by="vote_average.desc",
                vote_count_gte=500,
            )
            for m in discover.get("results", [])[:6]:
                add_movie(m)

    return movies[:8]


async def get_music_recommendations(ctx: dict) -> list:
    """
    Build Spotify queries from genres + keywords.
    Falls back to Last.fm (free, no key needed for basic calls) if Spotify is unavailable.
    """
    music_data = await _spotify_music(ctx)
    if not music_data:
        logger.info("Spotify unavailable — trying Last.fm fallback")
        music_data = await _lastfm_music(ctx)
    return music_data


async def _spotify_music(ctx: dict) -> list:
    """Try Spotify first."""
    try:
        sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
            )
        )

        title    = ctx["title"]
        genres   = ctx["genres"][:2]
        keywords = ctx["keywords"][:3]

        queries = [
            f"{title} soundtrack",
            f"{title} score",
        ]
        for g in genres:
            queries.append(f"{g} cinematic score")
        if keywords:
            queries.append(f"{' '.join(keywords[:2])} music")
        if ctx.get("director"):
            queries.append(f"{ctx['director']} film score")

        all_tracks, seen = [], set()

        for q in queries[:5]:
            try:
                res = sp.search(q=q, type="track", limit=10)
                for t in res["tracks"]["items"]:
                    if t["id"] not in seen:
                        seen.add(t["id"])
                        all_tracks.append(t)
            except Exception as e:
                logger.warning(f"Spotify query '{q}' failed: {e}")

        if not all_tracks:
            return []

        all_tracks.sort(key=lambda t: t["popularity"], reverse=True)

        music_data = []
        for track in all_tracks[:6]:
            try:
                artist      = track["artists"][0]
                artist_info = sp.artist(artist["id"])
                image       = (
                    artist_info["images"][0]["url"]
                    if artist_info.get("images")
                    else "https://via.placeholder.com/300x300?text=Music"
                )
                music_data.append({
                    "title"      : track["name"],
                    "artist"     : artist["name"],
                    "album"      : track["album"]["name"],
                    "rating"     : round(track["popularity"] / 20, 1),
                    "description": f"Recommended for fans of {title}",
                    "image"      : image,
                    "preview_url": track.get("preview_url"),
                    "spotify_url": track["external_urls"]["spotify"],
                    "source"     : "spotify",
                })
            except Exception as e:
                logger.warning(f"Error processing Spotify track: {e}")

        return music_data

    except Exception as e:
        logger.error(f"Spotify error: {e}")
        return []


async def _lastfm_music(ctx: dict) -> list:
    """
    iTunes Search API — completely free, no key required.
    Search for movie soundtracks and genre-based music.
    """
    title   = ctx["title"]
    genres  = ctx["genres"]

    # Map film genre → iTunes genre term
    genre_terms = {
        "Science Fiction": "electronic",
        "Action"         : "rock",
        "Thriller"       : "alternative",
        "Horror"         : "metal",
        "Drama"          : "indie",
        "Romance"        : "pop",
        "Comedy"         : "pop",
        "Fantasy"        : "soundtrack",
        "Mystery"        : "jazz",
        "Crime"          : "hip-hop",
        "Animation"      : "soundtrack",
        "Adventure"      : "soundtrack",
        "History"        : "classical",
        "War"            : "classical",
    }

    queries = [f"{title} soundtrack", f"{title} score"]
    for g in genres[:2]:
        term = genre_terms.get(g)
        if term:
            queries.append(term)

    music_data = []
    seen = set()

    try:
        async with httpx.AsyncClient() as client:
            for q in queries[:3]:
                try:
                    r = await client.get(
                        "https://itunes.apple.com/search",
                        params={
                            "term"      : q,
                            "media"     : "music",
                            "entity"    : "song",
                            "limit"     : 5,
                            "country"   : "us",
                        },
                        timeout=8,
                    )
                    if r.status_code != 200:
                        continue
                    results = r.json().get("results", [])
                    for t in results:
                        track_id = t.get("trackId")
                        if not track_id or track_id in seen:
                            continue
                        seen.add(track_id)
                        artwork = t.get("artworkUrl100", "https://via.placeholder.com/300x300?text=Music")
                        # Upgrade thumbnail resolution
                        artwork = artwork.replace("100x100", "300x300")
                        music_data.append({
                            "title"      : t.get("trackName", "Unknown"),
                            "artist"     : t.get("artistName", "Unknown"),
                            "album"      : t.get("collectionName", ""),
                            "rating"     : round(t.get("trackTimeMillis", 0) / 60000 / 10, 1),
                            "description": f"Recommended for fans of {title}",
                            "image"      : artwork,
                            "preview_url": t.get("previewUrl"),
                            "spotify_url": t.get("trackViewUrl", ""),
                            "source"     : "itunes",
                        })
                except Exception as e:
                    logger.warning(f"iTunes query '{q}' failed: {e}")

                if len(music_data) >= 6:
                    break

    except Exception as e:
        logger.error(f"iTunes fallback error: {e}")

    return music_data[:6]


async def get_book_recommendations(client: httpx.AsyncClient, ctx: dict) -> list:
    """
    Build Open Library queries using the movie's genre + keywords,
    not just its title.  Gives semantically related books instead of
    a novel named after the film.
    """
    title    = ctx["title"]
    genres   = ctx["genres"]
    keywords = ctx["keywords"]

    # Map film genres to literary genres / subjects
    genre_map = {
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

    queries = []

    # 1 – Direct title (fans who want the novelization / tie-in)
    queries.append(title)

    # 2 – Genre-driven subjects
    for g in genres[:2]:
        mapped = genre_map.get(g, g.lower())
        queries.append(mapped)

    # 3 – Keyword-driven subjects
    if keywords:
        queries.append(" ".join(keywords[:3]))

    # 4 – Combine first genre + keyword
    if genres and keywords:
        queries.append(f"{genres[0]} {keywords[0]}")

    books, seen = [], set()

    async def fetch_query(q: str):
        try:
            r = await client.get(
                "https://openlibrary.org/search.json",
                params={"q": q, "limit": 5, "fields": "key,title,author_name,cover_i,subject,first_publish_year,ratings_average,first_sentence"},
                timeout=10,
            )
            r.raise_for_status()
            return r.json().get("docs", [])
        except Exception as e:
            logger.warning(f"Open Library query '{q}' failed: {e}")
            return []

    results = await asyncio.gather(*[fetch_query(q) for q in queries[:4]])

    for docs in results:
        for doc in docs:
            key = doc.get("key", "")
            if key in seen:
                continue
            seen.add(key)

            cover_id  = doc.get("cover_i")
            thumbnail = (
                f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                if cover_id
                else "https://via.placeholder.com/128x192?text=Book"
            )

            desc = doc.get("first_sentence", ["No description available."])
            if isinstance(desc, list):
                desc = desc[0] if desc else "No description available."
            if len(str(desc)) > 200:
                desc = str(desc)[:197] + "..."

            rating = doc.get("ratings_average")
            books.append({
                "title"    : doc.get("title", "No title"),
                "authors"  : doc.get("author_name", ["Unknown Author"]),
                "description": str(desc),
                "thumbnail": thumbnail,
                "rating"   : round(float(rating), 1) if rating else "N/A",
                "genre"    : doc.get("subject", ["General"])[0] if doc.get("subject") else "General",
                "year"     : doc.get("first_publish_year", "Unknown"),
            })

        if len(books) >= 6:
            break

    return books[:6]


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request):
    return templates.TemplateResponse("auth.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "timestamp": datetime.now().isoformat()}


@app.get("/movie-details/{movie_id}")
async def movie_details(movie_id: int):
    cached = cache_get(f"details_{movie_id}")
    if cached:
        return cached

    async with httpx.AsyncClient() as client:
        try:
            details, credits, videos = await asyncio.gather(
                tmdb_get(client, f"/movie/{movie_id}"),
                tmdb_get(client, f"/movie/{movie_id}/credits"),
                tmdb_get(client, f"/movie/{movie_id}/videos"),
            )
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Movie not found: {e}")

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

    result = {
        "title"   : details.get("title"),
        "overview": details.get("overview"),
        "rating"  : details.get("vote_average"),
        "release" : details.get("release_date"),
        "genres"  : [g["name"] for g in details.get("genres", [])],
        "runtime" : details.get("runtime"),
        "cast"    : cast,
        "trailer" : trailer,
    }
    cache_set(f"details_{movie_id}", result)
    return result


@app.post("/recommend")
async def recommend(body: RecommendRequest):
    movie = body.movie.strip()
    if not movie:
        raise HTTPException(status_code=400, detail="Movie title is required")

    cache_key = f"rec_{movie.lower()}"
    cached = cache_get(cache_key)
    if cached:
        cached["meta"]["cached"] = True
        return cached

    start = datetime.now()
    logger.info(f"Recommendation request: '{movie}'")

    async with httpx.AsyncClient() as client:
        # Step 1: enrich context from TMDB (genres, keywords, cast)
        ctx = await get_movie_context(client, movie)
        logger.info(f"Context for '{movie}': genres={ctx['genres']}, keywords={ctx['keywords'][:5]}")

        # Step 2: fire all three recommendation calls concurrently
        movies_task = get_similar_movies(client, ctx)
        music_task  = get_music_recommendations(ctx)
        books_task  = get_book_recommendations(client, ctx)

        movies, music, books = await asyncio.gather(movies_task, music_task, books_task)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"Done in {elapsed:.2f}s → {len(movies)} movies, {len(music)} music, {len(books)} books")

    response = {
        "movies": movies,
        "music" : music,
        "books" : books,
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
    cache_set(cache_key, response)
    return response


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
