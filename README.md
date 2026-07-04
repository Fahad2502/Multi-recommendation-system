# RecoHub 🎬🎵📚

**Cross-domain recommendation engine** — enter a movie title and get intelligently matched movies, music, and books, driven by genre and thematic context extracted from TMDB.

> **Stack:** FastAPI · Python 3.10 · async/await · TMDB · Spotify/iTunes · Open Library · Bootstrap 5

---

## How it actually works

Most recommendation tools just search by title string. RecoHub is smarter:

1. **Context extraction** — TMDB's `/keywords` and `/credits` endpoints are queried *in parallel* to extract the film's genres, thematic keywords (e.g. *heist, memory, manipulation*), and director
2. **TMDB similar/recommendations** — uses TMDB's own collaborative-filter engine (`/movie/{id}/similar`, `/movie/{id}/recommendations`) instead of a plain text search
3. **Music from genre+keywords** — Spotify queried with combos like `"Science Fiction cinematic score"` or `"heist dreams music"`. Falls back to iTunes Search API (free, no key) if Spotify is quota-limited
4. **Books by theme** — Open Library queried concurrently for the film title, mapped literary genre (`"psychological thriller"`), keyword subjects, and genre+keyword combos

All three API calls fire **concurrently** with `asyncio.gather` — avg response ~3–4 s.

---

## Features

| Feature | Detail |
|---|---|
| Async backend | FastAPI + httpx, fully non-blocking |
| Smart context | Genres + keywords drive all recommendations |
| API docs | Auto-generated Swagger UI at `/docs` |
| Caching | 1-hour in-memory TTL, <50 ms on cache hit |
| Music fallback | Spotify → iTunes (always returns results) |
| Movie detail modal | Cast, YouTube trailer embed, rating, genres |
| Context banner | Shows matched genres + keywords to user |
| Music previews | 30-sec iTunes previews play in-browser |
| Keyboard shortcuts | `Ctrl+K` focus search, `Esc` clear |
| Local favourites | localStorage, no account needed |
| Export | Download results as JSON or CSV |

---

## Tech stack

```
Backend    FastAPI 0.128  ·  Python 3.10  ·  uvicorn  ·  httpx (async)
APIs       TMDB  ·  Spotify (+ iTunes fallback)  ·  Open Library
Frontend   Vanilla JS  ·  Bootstrap 5  ·  Font Awesome
Auth       JWT (PyJWT)  ·  PBKDF2 hashing  [scaffold ready]
```

---

## Quick start

```bash
git clone https://github.com/<your-username>/recohub.git
cd recohub

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

cp .env.example .env          # add your API keys

python main.py
# http://localhost:8000
# http://localhost:8000/docs  ← Swagger UI
```

---

## API

### `POST /recommend`
```json
{ "movie": "Inception" }
```
Response:
```json
{
  "movies":  [{ "id": 27205, "title": "...", "rating": 8.4, "poster": "..." }],
  "music":   [{ "title": "...", "artist": "...", "preview_url": "..." }],
  "books":   [{ "title": "...", "authors": ["..."], "genre": "..." }],
  "context": { "matched_title": "Inception", "genres": ["Action","Sci-Fi"], "keywords": ["heist","dreams"] },
  "meta":    { "total_results": 20, "processing_time": "3.88s", "cached": false }
}
```

### `GET /movie-details/{id}`
Title, overview, rating, genres, runtime, top-3 cast, YouTube trailer key.

### `GET /docs`
Interactive Swagger UI — auto-generated.

---

## Project structure

```
recohub/
├── main.py              ← FastAPI app, all routes + recommendation logic
├── requirements.txt
├── .env.example
├── templates/
│   ├── index.html       ← Main UI (dark theme, animations)
│   └── auth.html        ← Auth scaffold
├── static/
│   ├── css/styles.css
│   └── js/
│       ├── main.js      ← Rendering, auth, API calls
│       ├── features.js  ← Keyboard shortcuts, favourites, CSV/JSON export
│       └── analytics.js ← Client-side event tracking
├── tests/
│   └── test_services.py
└── docs/
    ├── API.md
    └── DEPLOYMENT.md
```

---

## Architecture decisions

**FastAPI over Flask** — async-native; TMDB + Spotify + Open Library run concurrently. Free Pydantic validation and Swagger docs at zero cost.

**Genre/keyword context over title search** — searching `"Inception"` on Open Library returns the novelization. Searching `"science fiction heist memory"` returns *Dark Matter*, *Recursion* — actually relevant.

**iTunes as music fallback** — Spotify Client Credentials requires quota approval. iTunes Search API is public, rate-limit-free, and returns 30-sec preview MP3 URLs.

**Open Library over Google Books** — Google Books free tier shares 1 000 req/day across all unauthenticated callers. Open Library is fully open.

---

## Resume bullets

```
• Built RecoHub, an async cross-domain recommendation engine (FastAPI, Python 3.10)
  integrating TMDB, Spotify, and Open Library concurrently — avg response <4 s

• Replaced naive title-string search with TMDB genre/keyword context extraction,
  driving semantically matched music and book recommendations

• Engineered multi-source music fallback (Spotify → iTunes Search API) ensuring
  100 % uptime on music results regardless of API quota state

• Added in-memory response cache (1-hr TTL) reducing repeat-query latency
  from ~4 s to < 50 ms

• Auto-generated REST API docs (OpenAPI / Swagger) via FastAPI with Pydantic
  request validation
```

---

## License

MIT
