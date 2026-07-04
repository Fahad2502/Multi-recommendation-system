"""
RecoHub — Test Suite
Tests main.py functions using mocks so no real API calls are made.
Run: pytest tests/ -v
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── helpers ────────────────────────────────────────────────────────────────────
def async_return(value):
    """Wrap a value so it can be awaited."""
    f = asyncio.Future()
    f.set_result(value)
    return f


# ── Cache tests ────────────────────────────────────────────────────────────────
class TestCache:
    def test_cache_miss_returns_none(self):
        from main import cache_get, _cache
        _cache.clear()
        assert cache_get("nonexistent_key") is None

    def test_cache_set_then_get(self):
        from main import cache_get, cache_set, _cache
        _cache.clear()
        cache_set("test_key", {"data": 42})
        result = cache_get("test_key")
        assert result == {"data": 42}

    def test_cache_returns_none_after_expiry(self):
        from main import cache_get, _cache
        from datetime import datetime, timedelta
        _cache.clear()
        # Manually insert an expired entry (ts = 2 hours ago)
        _cache["old_key"] = {
            "data": "stale",
            "ts": datetime.now() - timedelta(hours=2)
        }
        assert cache_get("old_key") is None

    def test_cache_different_keys_are_isolated(self):
        from main import cache_get, cache_set, _cache
        _cache.clear()
        cache_set("key_a", "value_a")
        cache_set("key_b", "value_b")
        assert cache_get("key_a") == "value_a"
        assert cache_get("key_b") == "value_b"
        assert cache_get("key_c") is None


# ── Context extraction tests ───────────────────────────────────────────────────
MOCK_SEARCH = {
    "results": [{"id": 27205, "title": "Inception", "popularity": 100.0}]
}
MOCK_DETAILS = {
    "title": "Inception",
    "overview": "A thief who steals corporate secrets through dreams.",
    "vote_average": 8.8,
    "genres": [{"name": "Action"}, {"name": "Science Fiction"}, {"name": "Adventure"}],
    "release_date": "2010-07-16",
    "runtime": 148,
}
MOCK_KEYWORDS = {
    "keywords": [
        {"name": "mission"}, {"name": "dreams"}, {"name": "heist"},
        {"name": "memory"}, {"name": "manipulation"}
    ]
}
MOCK_CREDITS = {
    "cast": [
        {"name": "Leonardo DiCaprio"}, {"name": "Joseph Gordon-Levitt"},
        {"name": "Elliot Page"}, {"name": "Tom Hardy"},
    ],
    "crew": [{"name": "Christopher Nolan", "job": "Director"}]
}


@pytest.mark.asyncio
class TestMovieContext:
    async def test_context_extraction_returns_correct_fields(self):
        from main import get_movie_context

        call_map = {
            "/search/movie": MOCK_SEARCH,
            f"/movie/27205": MOCK_DETAILS,
            f"/movie/27205/keywords": MOCK_KEYWORDS,
            f"/movie/27205/credits": MOCK_CREDITS,
        }

        async def fake_tmdb(client, path, **params):
            for key, value in call_map.items():
                if path.endswith(key.split("/")[-1]) or path == key:
                    return value
            return {}

        with patch("main.tmdb_get", side_effect=fake_tmdb):
            import httpx
            async with httpx.AsyncClient() as client:
                ctx = await get_movie_context(client, "Inception")

        assert ctx["title"] == "Inception"
        assert "Action" in ctx["genres"]
        assert "Science Fiction" in ctx["genres"]
        assert "dreams" in ctx["keywords"]
        assert ctx["director"] == "Christopher Nolan"
        assert "Leonardo DiCaprio" in ctx["cast_names"]

    async def test_context_returns_fallback_when_no_results(self):
        from main import get_movie_context

        async def fake_tmdb(client, path, **params):
            return {"results": []}

        with patch("main.tmdb_get", side_effect=fake_tmdb):
            import httpx
            async with httpx.AsyncClient() as client:
                ctx = await get_movie_context(client, "XYZNOTAMOVIE")

        assert ctx["movie_id"] is None
        assert ctx["genres"] == []
        assert ctx["keywords"] == []
        assert ctx["title"] == "XYZNOTAMOVIE"


# ── Similar movies tests ───────────────────────────────────────────────────────
MOCK_SIMILAR = {
    "results": [
        {"id": 1, "title": "The Matrix", "poster_path": "/m.jpg",
         "release_date": "1999-03-31", "vote_average": 8.7, "overview": "A hacker discovers reality."},
        {"id": 2, "title": "Interstellar", "poster_path": "/i.jpg",
         "release_date": "2014-11-07", "vote_average": 8.6, "overview": "Space travel."},
    ]
}
MOCK_RECO = {"results": []}

MOCK_CTX = {
    "movie_id": 27205,
    "title": "Inception",
    "genres": ["Action", "Science Fiction"],
    "keywords": ["dreams", "heist"],
    "director": "Christopher Nolan",
}

@pytest.mark.asyncio
class TestSimilarMovies:
    async def test_returns_movies_with_posters(self):
        from main import get_similar_movies

        async def fake_tmdb(client, path, **params):
            if "similar" in path:
                return MOCK_SIMILAR
            if "recommendations" in path:
                return MOCK_RECO
            return {}

        with patch("main.tmdb_get", side_effect=fake_tmdb):
            import httpx
            async with httpx.AsyncClient() as client:
                movies = await get_similar_movies(client, MOCK_CTX)

        assert len(movies) >= 2
        assert all("poster" in m for m in movies)
        assert all("title" in m for m in movies)
        assert all("rating" in m for m in movies)

    async def test_skips_movies_without_poster(self):
        from main import get_similar_movies

        no_poster_results = {
            "results": [
                {"id": 99, "title": "No Poster Movie", "poster_path": None,
                 "release_date": "2020-01-01", "vote_average": 5.0, "overview": ""},
            ]
        }

        async def fake_tmdb(client, path, **params):
            if "similar" in path:
                return no_poster_results
            return {"results": []}

        with patch("main.tmdb_get", side_effect=fake_tmdb):
            import httpx
            async with httpx.AsyncClient() as client:
                movies = await get_similar_movies(client, MOCK_CTX)

        assert all(m["id"] != 99 for m in movies)

    async def test_returns_empty_when_no_movie_id(self):
        from main import get_similar_movies
        import httpx
        ctx_no_id = {**MOCK_CTX, "movie_id": None}
        async with httpx.AsyncClient() as client:
            result = await get_similar_movies(client, ctx_no_id)
        assert result == []


# ── Music fallback tests ───────────────────────────────────────────────────────
@pytest.mark.asyncio
class TestMusicFallback:
    async def test_itunes_fallback_returns_tracks(self):
        """When Spotify fails, iTunes fallback returns music data."""
        from main import _lastfm_music  # this is the iTunes fallback function

        itunes_response = {
            "results": [
                {
                    "trackId": 111,
                    "trackName": "Time",
                    "artistName": "Hans Zimmer",
                    "collectionName": "Inception OST",
                    "artworkUrl100": "https://example.com/art100x100.jpg",
                    "previewUrl": "https://example.com/preview.m4a",
                    "trackViewUrl": "https://music.apple.com/track/111",
                    "trackTimeMillis": 258000,
                },
                {
                    "trackId": 222,
                    "trackName": "Dream Is Collapsing",
                    "artistName": "Hans Zimmer",
                    "collectionName": "Inception OST",
                    "artworkUrl100": "https://example.com/art2100x100.jpg",
                    "previewUrl": "https://example.com/preview2.m4a",
                    "trackViewUrl": "https://music.apple.com/track/222",
                    "trackTimeMillis": 175000,
                },
            ]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = itunes_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            tracks = await _lastfm_music(MOCK_CTX)

        assert len(tracks) >= 1
        assert tracks[0]["source"] == "itunes"
        assert "300x300" in tracks[0]["image"]  # resolution was upgraded
        assert tracks[0]["preview_url"] is not None

    async def test_itunes_deduplicates_tracks(self):
        """Same trackId from multiple queries should appear only once."""
        from main import _lastfm_music

        duplicate_response = {
            "results": [
                {"trackId": 333, "trackName": "Dupe", "artistName": "Artist",
                 "collectionName": "Album", "artworkUrl100": "https://x.com/100x100.jpg",
                 "previewUrl": None, "trackViewUrl": "", "trackTimeMillis": 200000},
            ]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = duplicate_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            tracks = await _lastfm_music(MOCK_CTX)

        ids = [t["title"] for t in tracks]
        assert len(ids) == len(set(ids)), "Duplicate track titles found"


# ── Book recommendation tests ──────────────────────────────────────────────────
@pytest.mark.asyncio
class TestBookRecommendations:
    async def test_returns_books_with_required_fields(self):
        from main import get_book_recommendations

        open_library_response = {
            "docs": [
                {
                    "key": "/works/OL111W",
                    "title": "Dark Matter",
                    "author_name": ["Blake Crouch"],
                    "cover_i": 9999,
                    "subject": ["Science Fiction", "Thriller"],
                    "first_publish_year": 2016,
                    "ratings_average": 4.1,
                    "first_sentence": ["Jason Dessen is walking home."],
                },
                {
                    "key": "/works/OL222W",
                    "title": "Recursion",
                    "author_name": ["Blake Crouch"],
                    "cover_i": None,
                    "subject": ["Science Fiction"],
                    "first_publish_year": 2019,
                    "ratings_average": None,
                    "first_sentence": [],
                },
            ]
        }

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = open_library_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            import httpx
            async with httpx.AsyncClient() as client:
                books = await get_book_recommendations(client, MOCK_CTX)

        assert len(books) >= 1
        for book in books:
            assert "title" in book
            assert "authors" in book
            assert "thumbnail" in book
            assert "genre" in book

    async def test_no_cover_uses_placeholder(self):
        from main import get_book_recommendations

        response = {
            "docs": [{
                "key": "/works/OL333W",
                "title": "No Cover Book",
                "author_name": ["Unknown"],
                "cover_i": None,
                "subject": ["Fiction"],
                "first_publish_year": 2000,
                "ratings_average": None,
                "first_sentence": [],
            }]
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            import httpx
            async with httpx.AsyncClient() as client:
                books = await get_book_recommendations(client, MOCK_CTX)

        assert books[0]["thumbnail"] == "https://via.placeholder.com/128x192?text=Book"

    async def test_deduplicates_by_key(self):
        """Same Open Library key from multiple queries should appear once."""
        from main import get_book_recommendations

        same_doc = {
            "key": "/works/OL999W", "title": "Duplicate", "author_name": ["A"],
            "cover_i": 1, "subject": ["Fiction"], "first_publish_year": 2020,
            "ratings_average": 3.5, "first_sentence": ["Start."],
        }
        response = {"docs": [same_doc]}

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            import httpx
            async with httpx.AsyncClient() as client:
                books = await get_book_recommendations(client, MOCK_CTX)

        titles = [b["title"] for b in books]
        assert titles.count("Duplicate") == 1


# ── FastAPI route integration tests ───────────────────────────────────────────
from fastapi.testclient import TestClient
from main import app, _cache

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_has_required_fields(self):
        r = client.get("/health")
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data


class TestRecommendEndpoint:
    def test_empty_query_returns_400(self):
        r = client.post("/recommend", json={"movie": ""})
        assert r.status_code == 400

    def test_missing_body_returns_422(self):
        r = client.post("/recommend", json={})
        assert r.status_code == 422

    def test_cached_response_is_served(self):
        """If the cache already has a result, it should be returned without API calls."""
        _cache["rec_testcachedmovie"] = {
            "data": {
                "movies": [{"id": 1, "title": "Cached Movie", "poster": "", "rating": 8.0,
                            "release_date": "2020-01-01", "overview": ""}],
                "music": [],
                "books": [],
                "context": {"matched_title": "TestCachedMovie", "genres": [], "keywords": []},
                "meta": {"query": "TestCachedMovie", "total_results": 1,
                         "processing_time": "0.00s", "cached": False},
            },
            "ts": __import__("datetime").datetime.now(),
        }
        r = client.post("/recommend", json={"movie": "TestCachedMovie"})
        assert r.status_code == 200
        data = r.json()
        assert data["meta"]["cached"] is True
        assert data["movies"][0]["title"] == "Cached Movie"

    def test_response_schema_structure(self):
        """Cached response must contain all expected top-level keys."""
        _cache["rec_schematest"] = {
            "data": {
                "movies": [], "music": [], "books": [],
                "context": {"matched_title": "Schema", "genres": [], "keywords": []},
                "meta": {"query": "schema", "total_results": 0,
                         "processing_time": "0.00s", "cached": False},
            },
            "ts": __import__("datetime").datetime.now(),
        }
        r = client.post("/recommend", json={"movie": "SchemaTest"})
        assert r.status_code == 200
        data = r.json()
        for key in ("movies", "music", "books", "context", "meta"):
            assert key in data, f"Missing key: {key}"


class TestMovieDetailsEndpoint:
    def test_cached_movie_details_returned(self):
        _cache["details_27205"] = {
            "data": {
                "title": "Inception", "overview": "A thief...", "rating": 8.8,
                "release": "2010-07-16", "genres": ["Action", "Sci-Fi"],
                "runtime": 148, "cast": [], "trailer": "YoHD9XEInc0",
            },
            "ts": __import__("datetime").datetime.now(),
        }
        r = client.get("/movie-details/27205")
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Inception"
        assert data["trailer"] == "YoHD9XEInc0"

    def test_movie_details_has_cast_and_trailer_fields(self):
        _cache["details_99999"] = {
            "data": {
                "title": "Test Movie", "overview": "", "rating": 7.0,
                "release": "2023-01-01", "genres": ["Drama"],
                "runtime": 100,
                "cast": [{"name": "Actor One", "profile": "https://via.placeholder.com/80"}],
                "trailer": None,
            },
            "ts": __import__("datetime").datetime.now(),
        }
        r = client.get("/movie-details/99999")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["cast"], list)
        assert "trailer" in data

