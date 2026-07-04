"""
RecoHub — Test Suite
Run: pytest tests/ -v
All network calls are mocked — no API keys or internet needed.
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── app under test ─────────────────────────────────────────────────────────────
from app.factory import create_app
from app.core import cache

app    = create_app()
client = TestClient(app)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Cache
# ══════════════════════════════════════════════════════════════════════════════
class TestCache:
    def setup_method(self):
        cache.clear()

    def test_miss_returns_none(self):
        assert cache.get("missing") is None

    def test_set_then_get(self):
        cache.set("k", {"x": 1})
        assert cache.get("k") == {"x": 1}

    def test_expired_entry_returns_none(self):
        from app.core.cache import _store
        _store["old"] = {"data": "stale", "ts": datetime.now() - timedelta(hours=2)}
        assert cache.get("old") is None

    def test_keys_are_isolated(self):
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") is None


# ══════════════════════════════════════════════════════════════════════════════
# 2. TMDB service — context extraction
# ══════════════════════════════════════════════════════════════════════════════
SEARCH_RESULT   = {"results": [{"id": 27205, "title": "Inception", "popularity": 100.0}]}
MOVIE_DETAILS   = {"title": "Inception", "overview": "A thief.", "vote_average": 8.8,
                   "genres": [{"name": "Action"}, {"name": "Science Fiction"}],
                   "release_date": "2010-07-16", "runtime": 148}
MOVIE_KEYWORDS  = {"keywords": [{"name": "dreams"}, {"name": "heist"}, {"name": "mission"}]}
MOVIE_CREDITS   = {
    "cast": [{"name": "Leonardo DiCaprio"}, {"name": "Joseph Gordon-Levitt"}],
    "crew": [{"name": "Christopher Nolan", "job": "Director"}],
}


def _make_tmdb_mock(path_map: dict):
    """Return an async fake for app.services.tmdb._get based on path_map."""
    async def fake_get(client, path, **params):
        for key, value in path_map.items():
            if path.endswith(key):
                return value
        return {}
    return fake_get


@pytest.mark.asyncio
class TestTmdbContext:
    async def test_extracts_genres_keywords_director(self):
        from app.services.tmdb import get_movie_context
        import httpx

        path_map = {
            "/search/movie": SEARCH_RESULT,
            "/movie/27205"  : MOVIE_DETAILS,
            "/keywords"     : MOVIE_KEYWORDS,
            "/credits"      : MOVIE_CREDITS,
        }
        with patch("app.services.tmdb._get", side_effect=_make_tmdb_mock(path_map)):
            async with httpx.AsyncClient() as c:
                ctx = await get_movie_context(c, "Inception")

        assert ctx["title"] == "Inception"
        assert "Action" in ctx["genres"]
        assert "dreams" in ctx["keywords"]
        assert ctx["director"] == "Christopher Nolan"

    async def test_empty_search_returns_fallback(self):
        from app.services.tmdb import get_movie_context
        import httpx

        async def no_results(client, path, **params):
            return {"results": []}

        with patch("app.services.tmdb._get", side_effect=no_results):
            async with httpx.AsyncClient() as c:
                ctx = await get_movie_context(c, "XYZFAKE")

        assert ctx["movie_id"] is None
        assert ctx["genres"] == []


# ══════════════════════════════════════════════════════════════════════════════
# 3. TMDB service — similar movies
# ══════════════════════════════════════════════════════════════════════════════
MOCK_CTX = {
    "movie_id": 27205, "title": "Inception",
    "genres": ["Action", "Science Fiction"],
    "keywords": ["dreams", "heist"],
    "director": "Christopher Nolan",
}
SIMILAR_RESULTS = {
    "results": [
        {"id": 1, "title": "The Matrix", "poster_path": "/m.jpg",
         "release_date": "1999-03-31", "vote_average": 8.7, "overview": "Neo."},
        {"id": 2, "title": "Interstellar", "poster_path": "/i.jpg",
         "release_date": "2014-11-07", "vote_average": 8.6, "overview": "Space."},
    ]
}


@pytest.mark.asyncio
class TestSimilarMovies:
    async def test_returns_cards_with_required_fields(self):
        from app.services.tmdb import get_similar_movies
        import httpx

        async def fake(client, path, **params):
            if "similar" in path:       return SIMILAR_RESULTS
            if "recommendations" in path: return {"results": []}
            return {}

        with patch("app.services.tmdb._get", side_effect=fake):
            async with httpx.AsyncClient() as c:
                movies = await get_similar_movies(c, MOCK_CTX)

        assert len(movies) >= 2
        for m in movies:
            assert all(k in m for k in ("id", "title", "poster", "rating", "overview"))

    async def test_skips_movies_without_poster(self):
        from app.services.tmdb import get_similar_movies
        import httpx

        no_poster = {"results": [
            {"id": 99, "title": "No Poster", "poster_path": None,
             "vote_average": 5.0, "overview": "", "release_date": ""},
        ]}

        async def fake(client, path, **params):
            if "similar" in path: return no_poster
            return {"results": []}

        with patch("app.services.tmdb._get", side_effect=fake):
            async with httpx.AsyncClient() as c:
                movies = await get_similar_movies(c, MOCK_CTX)

        assert all(m["id"] != 99 for m in movies)

    async def test_empty_when_no_movie_id(self):
        from app.services.tmdb import get_similar_movies
        import httpx

        ctx = {**MOCK_CTX, "movie_id": None}
        async with httpx.AsyncClient() as c:
            assert await get_similar_movies(c, ctx) == []


# ══════════════════════════════════════════════════════════════════════════════
# 4. Music service — iTunes fallback
# ══════════════════════════════════════════════════════════════════════════════
ITUNES_RESPONSE = {
    "results": [
        {"trackId": 111, "trackName": "Time", "artistName": "Hans Zimmer",
         "collectionName": "Inception OST", "artworkUrl100": "https://x.com/100x100bb.jpg",
         "previewUrl": "https://x.com/preview.m4a", "trackViewUrl": "https://music.apple.com/1",
         "trackTimeMillis": 258000},
        {"trackId": 222, "trackName": "Dream Is Collapsing", "artistName": "Hans Zimmer",
         "collectionName": "Inception OST", "artworkUrl100": "https://x.com/100x100bb.jpg",
         "previewUrl": "https://x.com/preview2.m4a", "trackViewUrl": "https://music.apple.com/2",
         "trackTimeMillis": 175000},
    ]
}


@pytest.mark.asyncio
class TestMusicFallback:
    async def test_itunes_returns_tracks_with_source_field(self):
        from app.services.music import _from_itunes

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ITUNES_RESPONSE

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            tracks = await _from_itunes(MOCK_CTX)

        assert len(tracks) >= 1
        assert all(t["source"] == "itunes" for t in tracks)

    async def test_artwork_resolution_upgraded(self):
        from app.services.music import _from_itunes

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ITUNES_RESPONSE

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            tracks = await _from_itunes(MOCK_CTX)

        assert all("300x300" in t["image"] for t in tracks)

    async def test_deduplicates_by_track_id(self):
        from app.services.music import _from_itunes

        dup = {"results": [
            {"trackId": 333, "trackName": "Dupe", "artistName": "A",
             "collectionName": "B", "artworkUrl100": "https://x.com/100x100bb.jpg",
             "previewUrl": None, "trackViewUrl": "", "trackTimeMillis": 200000},
        ]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = dup

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            tracks = await _from_itunes(MOCK_CTX)

        assert len([t for t in tracks if t["title"] == "Dupe"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 5. Books service
# ══════════════════════════════════════════════════════════════════════════════
OL_DOCS = {
    "docs": [
        {"key": "/works/OL1W", "title": "Dark Matter", "author_name": ["Blake Crouch"],
         "cover_i": 9999, "subject": ["Science Fiction"], "first_publish_year": 2016,
         "ratings_average": 4.1, "first_sentence": ["Jason Dessen is walking home."]},
        {"key": "/works/OL2W", "title": "Recursion", "author_name": ["Blake Crouch"],
         "cover_i": None, "subject": ["Science Fiction"], "first_publish_year": 2019,
         "ratings_average": None, "first_sentence": []},
    ]
}


@pytest.mark.asyncio
class TestBookService:
    async def test_returns_books_with_required_fields(self):
        from app.services.books import get_book_recommendations
        import httpx

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = OL_DOCS

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with httpx.AsyncClient() as c:
                books = await get_book_recommendations(c, MOCK_CTX)

        assert len(books) >= 1
        for b in books:
            assert all(k in b for k in ("title", "authors", "thumbnail", "genre", "year"))

    async def test_no_cover_id_uses_placeholder(self):
        from app.services.books import get_book_recommendations, _COVER_PLACEHOLDER
        import httpx

        no_cover = {"docs": [
            {"key": "/works/OL3W", "title": "No Cover", "author_name": ["X"],
             "cover_i": None, "subject": ["Fiction"], "first_publish_year": 2020,
             "ratings_average": None, "first_sentence": []},
        ]}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = no_cover

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with httpx.AsyncClient() as c:
                books = await get_book_recommendations(c, MOCK_CTX)

        assert books[0]["thumbnail"] == _COVER_PLACEHOLDER

    async def test_deduplicates_by_ol_key(self):
        from app.services.books import get_book_recommendations
        import httpx

        same_doc = {"docs": [
            {"key": "/works/OL99W", "title": "Same", "author_name": ["A"],
             "cover_i": 1, "subject": ["Fiction"], "first_publish_year": 2021,
             "ratings_average": 3.5, "first_sentence": ["Start."]},
        ]}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = same_doc

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with httpx.AsyncClient() as c:
                books = await get_book_recommendations(c, MOCK_CTX)

        assert len([b for b in books if b["title"] == "Same"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 6. HTTP routes via TestClient
# ══════════════════════════════════════════════════════════════════════════════
class TestHealthRoute:
    def test_200_with_expected_fields(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data


class TestRecommendRoute:
    def setup_method(self):
        cache.clear()

    def test_empty_movie_returns_422(self):
        r = client.post("/recommend", json={"movie": ""})
        assert r.status_code == 422

    def test_whitespace_only_returns_400(self):
        r = client.post("/recommend", json={"movie": "   "})
        # Pydantic strips whitespace and raises ValueError → 422
        assert r.status_code == 422

    def test_missing_field_returns_422(self):
        r = client.post("/recommend", json={})
        assert r.status_code == 422

    def test_cached_result_is_served(self):
        cache.set("rec_cachedfilm", {
            "movies": [], "music": [], "books": [],
            "context": {"matched_title": "CachedFilm", "genres": [], "keywords": []},
            "meta": {"query": "cachedfilm", "total_results": 0,
                     "processing_time": "0.00s", "cached": False},
        })
        r = client.post("/recommend", json={"movie": "CachedFilm"})
        assert r.status_code == 200
        assert r.json()["meta"]["cached"] is True

    def test_response_has_all_top_level_keys(self):
        cache.set("rec_schemacheck", {
            "movies": [], "music": [], "books": [],
            "context": {"matched_title": "X", "genres": [], "keywords": []},
            "meta": {"query": "x", "total_results": 0,
                     "processing_time": "0.00s", "cached": False},
        })
        r = client.post("/recommend", json={"movie": "SchemaCheck"})
        for key in ("movies", "music", "books", "context", "meta"):
            assert key in r.json()


class TestMovieDetailsRoute:
    def setup_method(self):
        cache.clear()

    def test_cached_detail_returned(self):
        cache.set("details_27205", {
            "title": "Inception", "overview": "A thief.", "rating": 8.8,
            "release": "2010-07-16", "genres": ["Action"], "runtime": 148,
            "cast": [], "trailer": "YoHD9XEInc0",
        })
        r = client.get("/movie-details/27205")
        assert r.status_code == 200
        assert r.json()["trailer"] == "YoHD9XEInc0"

    def test_response_has_cast_and_trailer_fields(self):
        cache.set("details_1", {
            "title": "Test", "overview": "", "rating": 7.0,
            "release": "2020-01-01", "genres": [], "runtime": 90,
            "cast": [{"name": "Actor", "profile": "https://via.placeholder.com/80"}],
            "trailer": None,
        })
        r = client.get("/movie-details/1")
        data = r.json()
        assert "cast" in data
        assert "trailer" in data
