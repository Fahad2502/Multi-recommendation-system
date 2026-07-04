# RecoHub — Deep Technical Analysis

## What the project does (one paragraph)

RecoHub takes a movie title as input and returns related content across three
domains — similar movies, thematically matched music, and relevant books — in a
single API call. Unlike a naive search that just queries each API with the raw
title string, RecoHub first extracts the film's genres, thematic keywords, and
director from TMDB, then uses that semantic context to drive all three downstream
recommendation queries concurrently. The result is a genuinely cross-domain
recommendation experience: searching "Inception" returns films like *The Matrix*
(not just other movies named "Inception"), music like *Action cinematic score*
tracks, and books in the *science fiction / psychological thriller* category
rather than novelizations of the film itself.

---

## Architecture — top level

```
Browser ──POST /recommend──► FastAPI (main.py)
                                │
                    ┌───────────┼───────────────┐
                    ▼           ▼               ▼
              get_similar   get_music_    get_book_
              _movies()    recommendations() recommendations()
                    │           │               │
                    ▼           ▼               ▼
                  TMDB       Spotify         Open Library
              /similar    (+ iTunes        (4 concurrent
              /reco        fallback)        queries)
              /discover
                    │
                    └── asyncio.gather (all 3 run simultaneously)
                                │
                         ◄──────┘
                     JSON response
                     (cached 1 hr)
```

Every piece of I/O is async (`httpx.AsyncClient`, `asyncio.gather`). No thread
blocking. On a cold request the app fires 8–10 HTTP calls total and completes
in ~3–4 seconds. On a cached request it returns in < 50 ms.

---

## Step-by-step request lifecycle

### Step 0 — Pydantic validation
FastAPI validates the request body against `RecommendRequest(movie: str)` before
any code runs. Empty string triggers HTTP 400. Missing field triggers HTTP 422.
This is free — no manual validation code needed.

### Step 1 — Cache check
```python
cache_key = f"rec_{movie.lower()}"
cached = cache_get(cache_key)
if cached:
    cached["meta"]["cached"] = True
    return cached
```
The in-memory dict `_cache` stores results keyed by lowercase movie name.
Each entry has a `ts` (timestamp). `cache_get` rejects entries older than 3600 s.
This is simple but effective for a single-process server — no Redis needed.

### Step 2 — Context extraction (`get_movie_context`)
This is the core innovation. Three TMDB calls fire in parallel:
```python
details, keywords_data, credits = await asyncio.gather(
    tmdb_get(client, f"/movie/{movie_id}"),          # genres, title, rating
    tmdb_get(client, f"/movie/{movie_id}/keywords"),  # thematic keywords
    tmdb_get(client, f"/movie/{movie_id}/credits"),   # cast, director
)
```
Result for "Inception":
```json
{
  "genres":   ["Action", "Science Fiction", "Adventure"],
  "keywords": ["mission", "dreams", "kidnapping", "spy", "heist", "memory"],
  "director": "Christopher Nolan",
  "cast_names": ["Leonardo DiCaprio", "Joseph Gordon-Levitt", ...]
}
```
This context object is passed to all three recommendation functions. None of
them ever see the raw user input string — they work from semantic metadata.

### Step 3 — Three recommendations fire concurrently
```python
movies, music, books = await asyncio.gather(
    get_similar_movies(client, ctx),
    get_music_recommendations(ctx),
    get_book_recommendations(client, ctx),
)
```
Wall clock time ≈ max(slowest single call) rather than sum of all calls.

### Step 4 — Response assembly and cache write
The result dict is stored in `_cache` and returned. On subsequent identical
queries the entire Step 2–4 pipeline is skipped.

---

## Movie recommendations — how accuracy works

**Old approach (naive):** `GET /search/movie?query=Inception`
→ Returns movies literally named "Inception". Misses all thematically related films.

**New approach:**
1. Search for the input, pick the highest-popularity result by TMDB's own score.
2. Call `/movie/{id}/recommendations` — TMDB's collaborative-filter engine,
   trained on what users who watched this film also watched.
3. Call `/movie/{id}/similar` — TMDB's content-based similarity (genre, cast, crew).
4. If fewer than 4 results, fall back to `/discover/movie?with_genres=X` — finds
   top-rated films in the same primary genre.
5. Deduplicate by TMDB ID, filter out anything without a poster image, cap at 8.

For "Inception" this returns: *The Dark Knight, Interstellar, The Prestige,
Shutter Island, Memento* — all genuinely related, none just named "Inception".

---

## Music recommendations — how accuracy + resilience work

### Query construction from context
Instead of searching "Inception" on Spotify, the app builds queries like:
- `"Inception soundtrack"` — direct
- `"Inception score"` — score-specific
- `"Action cinematic score"` — genre-based
- `"Science Fiction cinematic score"` — second genre
- `"mission dreams music"` — first two keywords combined
- `"Christopher Nolan film score"` — director-based

Each query hits Spotify's `/search` endpoint with `limit=10`. Tracks from all
queries are pooled, deduplicated by Spotify track ID, sorted by `popularity`
desc, and top 6 are taken.

### Two-tier fallback
```
Spotify available? ──yes──► use Spotify (rich metadata, popularity score)
       │
       no
       ▼
iTunes Search API (free, no auth, always available)
  → queries: "{title} soundtrack", "{title} score", "{genre_term}"
  → upgrades artwork: "100x100bb" → "300x300bb" for high-res images
  → returns 30-second preview MP3 URLs that play directly in the browser
```
The `source` field in each track indicates which API was used. The frontend
renders an Apple icon or Spotify icon accordingly.

### Rating calculation
- Spotify: `round(track.popularity / 20, 1)` → maps 0–100 to 0–5 scale
- iTunes: `round(trackTimeMillis / 60000 / 10, 1)` → loose approximation
  (longer tracks tend to be more substantial)

---

## Book recommendations — how accuracy works

### Query strategy (4 parallel queries to Open Library)

| Query # | Example for "Inception" | Rationale |
|---------|------------------------|-----------|
| 1 | `"Inception"` | Catch novelizations and tie-ins |
| 2 | `"action adventure"` | Primary genre mapped to literary genre |
| 3 | `"science fiction"` | Secondary genre |
| 4 | `"mission dreams heist"` | Top 3 keywords as subject terms |

Genre mapping table converts TMDB genres to Open Library subject terms:
```python
"Science Fiction" → "science fiction"
"Thriller"        → "psychological thriller"
"Crime"           → "crime fiction"
"History"         → "historical fiction"
```

All 4 queries fire concurrently with `asyncio.gather`. Results are deduplicated
by Open Library `key` (e.g. `/works/OL111W`). First 6 unique books are returned.

### Why Open Library over Google Books
Google Books free tier: 1,000 requests/day **shared** across all unauthenticated
callers (the project_number in the error message is Google's shared key). After
~10 searches the quota is exhausted.
Open Library: fully public API, no authentication, no rate limits documented,
no API key needed. Cover images are served from `covers.openlibrary.org`.

---

## Caching — design and trade-offs

```python
_cache: dict = {}                         # module-level singleton

def cache_get(key: str):
    entry = _cache.get(key)
    if entry and (datetime.now() - entry["ts"]).seconds < 3600:
        return entry["data"]
    return None

def cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": datetime.now()}
```

**Pros:** Zero dependencies, zero latency, zero config. Works immediately.
**Cons:** Cleared on every server restart. Not shared across multiple processes.
**Production upgrade path:** Replace with Redis (`redis-py` or `aioredis`).
The interface is intentionally simple so the swap is 2 lines of code.

Cache keys:
- `rec_{movie.lower()}` — full recommendation result (1 hr TTL)
- `details_{movie_id}` — single movie detail page (1 hr TTL)

---

## FastAPI — why and what it gives you

**Async:** Every route handler and helper is `async def`. FastAPI + uvicorn run
on an event loop, so while one request waits for TMDB to respond, the server
handles other requests. Equivalent Flask code would block the thread.

**Pydantic validation:**
```python
class RecommendRequest(BaseModel):
    movie: str
```
FastAPI automatically validates the request body, returns 422 with a detailed
error message for bad input, and shows the schema in Swagger UI. No manual
`if not data.get('movie')` needed (beyond the empty-string check for UX).

**Auto-generated docs:** `GET /docs` gives a live Swagger UI where you can
execute API calls from the browser. `GET /redoc` gives ReDoc. Both are generated
from the code's type annotations — no YAML to maintain.

**Error handling:**
```python
raise HTTPException(status_code=404, detail=f"Movie not found: {e}")
```
FastAPI serializes this to `{"detail": "Movie not found: ..."}` automatically.

---

## Frontend architecture

Three JavaScript classes, each with a single responsibility:

| File | Class | Responsibility |
|------|-------|----------------|
| `main.js` | `RecoAI` | API calls, rendering cards, modal, notifications, auth state |
| `features.js` | `AdvancedFeatures` | Keyboard shortcuts, localStorage favourites, JSON/CSV export |
| `analytics.js` | `Analytics` | Client-side event tracking (search, clicks, errors, page views) |

### Rendering pipeline
```
fetch POST /recommend
  → renderContextBanner(data.context)    // shows matched genres/keywords
  → renderResults(data)
      → createMovieCard × N
      → createMusicCard × N              // shows Preview + Apple/Spotify link
      → createBookCard × N
  → animateNumber() on stats bar         // count-up animation
```

### Context banner
The `context` object from the API is displayed to the user as genre/keyword
tags above the results. This is transparency — the user can see *why* they
got these recommendations ("Matched Inception — based on: Action · Sci-Fi ·
heist · dreams").

### Music card source detection
```javascript
const linkIcon  = track.source === 'itunes' ? 'fa-apple'   : 'fa-spotify';
const linkLabel = track.source === 'itunes' ? 'Apple Music' : 'Spotify';
```
The card adapts its icon and link label based on which API provided the track.

---

## Test coverage

22 tests, 0 failures. Tests are organized by component:

| Class | Tests | What's covered |
|-------|-------|----------------|
| `TestCache` | 4 | hit/miss, expiry, isolation |
| `TestMovieContext` | 2 | field extraction, empty-result fallback |
| `TestSimilarMovies` | 3 | poster filtering, no-id guard, card fields |
| `TestMusicFallback` | 2 | iTunes returns data, deduplication |
| `TestBookRecommendations` | 3 | required fields, placeholder thumbnail, deduplication |
| `TestHealthEndpoint` | 2 | status code, response fields |
| `TestRecommendEndpoint` | 4 | 400/422 errors, cache serving, schema |
| `TestMovieDetailsEndpoint` | 2 | cache serving, cast/trailer fields |

All tests use `unittest.mock` — no real HTTP calls, no API keys needed. The
async tests use `pytest-asyncio`. The route tests use FastAPI's `TestClient`.

Run: `pytest tests/ -v`

---

## Security considerations

- API keys are loaded from `.env` via `python-dotenv`. Never hardcoded in committed code (`.env` is gitignored).
- `.env.example` shows key names without values so contributors know what to add.
- Pydantic validates all inbound data — no raw `request.json()` dict access.
- TMDB movie IDs in `/movie-details/{movie_id}` are typed as `int` by FastAPI — no SQL injection surface, no string parsing needed.
- The app has no user-writable database in production; the auth scaffold (JWT + PBKDF2) is designed but not yet wired to routes.

---

## Performance numbers (measured)

| Scenario | Time |
|----------|------|
| Cold request (no cache) | 3.4 – 4.3 s |
| Warm request (cache hit) | < 50 ms |
| Cache TTL | 3600 s (1 hour) |
| Parallel API calls per request | 8 – 10 |
| Test suite | 22 tests / 0.92 s |

---

## What you'd do next (honest roadmap)

| Priority | Change | Why |
|----------|--------|-----|
| High | Wire Spotify app to a real developer account with quota | Current creds hit 403 on search |
| High | Add `pytest --cov` to measure line coverage | Currently no coverage report |
| Medium | Replace in-memory cache with Redis | Survives restarts, works multi-process |
| Medium | Complete JWT auth routes (register/login) | Scaffold exists in `templates/auth.html` |
| Medium | Move API keys to proper secrets manager | `.env` is fine for dev, not prod |
| Low | Add rate limiting (`slowapi`) | Prevent abuse |
| Low | Migrate to PostgreSQL for user data | File-based storage doesn't scale |
| Low | Add CI/CD (GitHub Actions) | Auto-run tests on push |
