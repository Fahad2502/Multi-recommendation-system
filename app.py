"""
RecoHub - Flask Backend
Cross-domain recommendation system: Movies, Music & Books
"""
from flask import Flask, render_template, request, jsonify
from rapidfuzz import process
import requests
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import logging
from datetime import datetime

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MOVIES_API_KEY        = os.getenv("MOVIES_API_KEY", "d071e08228154bfc3226692bdbd5318e")
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "49f4ca2258414e498596139510cce326")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "3ffe2874c6484a7aa6180d3b2e818d07")
TMDB_BASE             = "https://api.themoviedb.org/3"

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


# ── helpers ────────────────────────────────────────────────────────────────────

def tmdb(path, **params):
    """Make a TMDB GET request. Returns parsed JSON or empty dict on failure."""
    try:
        params["api_key"] = MOVIES_API_KEY
        params["language"] = "en-US"
        r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("TMDB %s failed: %s", path, e)
        return {}


def best_match(user_input, titles):
    match = process.extractOne(user_input, titles)
    return match[0] if match else user_input


# ── movie functions ────────────────────────────────────────────────────────────

def fetch_movie_details(movie_id):
    """Return title, overview, rating, cast, trailer for the modal."""
    movie   = tmdb(f"/movie/{movie_id}")
    credits = tmdb(f"/movie/{movie_id}/credits")
    videos  = tmdb(f"/movie/{movie_id}/videos")

    cast = [
        {
            "name": a["name"],
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
        "title"   : movie.get("title"),
        "overview": movie.get("overview"),
        "rating"  : movie.get("vote_average"),
        "release" : movie.get("release_date"),
        "genres"  : [g["name"] for g in movie.get("genres", [])],
        "runtime" : movie.get("runtime"),
        "cast"    : cast,
        "trailer" : trailer,
    }


def get_similar_movies(movie_name):
    """
    Search TMDB, pick best match, then pull /recommendations + /similar.
    Returns up to 8 movie cards with id, title, poster, rating, overview.
    """
    search  = tmdb("/search/movie", query=movie_name)
    results = search.get("results", [])
    if not results:
        return []

    # Pick best fuzzy match
    titles     = [m["title"] for m in results]
    best_title = best_match(movie_name, titles)
    chosen     = next((m for m in results if m["title"] == best_title), results[0])
    movie_id   = chosen["id"]

    reco_data = tmdb(f"/movie/{movie_id}/recommendations").get("results", [])
    sim_data  = tmdb(f"/movie/{movie_id}/similar").get("results", [])

    # Merge, deduplicate, sort by quality
    combined = {m["id"]: m for m in reco_data + sim_data}
    # Always include the searched movie first
    movies = []
    if chosen.get("poster_path"):
        movies.append({
            "id"          : chosen["id"],
            "title"       : chosen["title"],
            "poster"      : f"https://image.tmdb.org/t/p/w500{chosen['poster_path']}",
            "release_date": chosen.get("release_date", ""),
            "rating"      : round(chosen.get("vote_average", 0), 1),
            "overview"    : (chosen.get("overview", "")[:150] + "...") if chosen.get("overview") else "",
        })

    sorted_rest = sorted(
        combined.values(),
        key=lambda m: (m.get("vote_average", 0), m.get("popularity", 0)),
        reverse=True,
    )
    for m in sorted_rest:
        if len(movies) >= 8:
            break
        if m.get("poster_path") and m["id"] != chosen["id"]:
            movies.append({
                "id"          : m["id"],
                "title"       : m["title"],
                "poster"      : f"https://image.tmdb.org/t/p/w500{m['poster_path']}",
                "release_date": m.get("release_date", ""),
                "rating"      : round(m.get("vote_average", 0), 1),
                "overview"    : (m.get("overview", "")[:150] + "...") if m.get("overview") else "",
            })

    logger.info("Movies: returning %d results for '%s'", len(movies), movie_name)
    return movies


# ── music functions ────────────────────────────────────────────────────────────

def get_music_recommendations(movie_name):
    """Spotify first, iTunes fallback. Returns up to 6 tracks."""
    tracks = _spotify_music(movie_name)
    if not tracks:
        logger.info("Spotify unavailable — falling back to iTunes")
        tracks = _itunes_music(movie_name)
    return tracks


def _spotify_music(movie_name):
    try:
        sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
            )
        )
        queries    = [movie_name, f"{movie_name} soundtrack", f"{movie_name} score"]
        all_tracks = []
        seen       = set()

        for q in queries:
            try:
                res = sp.search(q=q, type="track", limit=10)
                for t in res["tracks"]["items"]:
                    if t["id"] not in seen:
                        seen.add(t["id"])
                        all_tracks.append(t)
            except Exception as e:
                logger.warning("Spotify query '%s' failed: %s", q, e)

        if not all_tracks:
            return []

        all_tracks.sort(key=lambda t: t["popularity"], reverse=True)
        music = []
        for track in all_tracks[:6]:
            try:
                artist      = track["artists"][0]
                artist_info = sp.artist(artist["id"])
                image       = (
                    artist_info["images"][0]["url"]
                    if artist_info.get("images")
                    else "https://via.placeholder.com/300x300?text=Music"
                )
                music.append({
                    "title"      : track["name"],
                    "artist"     : artist["name"],
                    "album"      : track["album"]["name"],
                    "rating"     : round(track["popularity"] / 20, 1),
                    "description": f"Recommended for fans of {movie_name}",
                    "image"      : image,
                    "preview_url": track.get("preview_url"),
                    "spotify_url": track["external_urls"]["spotify"],
                    "source"     : "spotify",
                })
            except Exception as e:
                logger.warning("Error processing Spotify track: %s", e)

        logger.info("Spotify: returning %d tracks", len(music))
        return music

    except Exception as e:
        logger.error("Spotify error: %s", e)
        return []


def _itunes_music(movie_name):
    """iTunes Search API — free, no key, returns 30-sec preview URLs."""
    queries    = [f"{movie_name} soundtrack", f"{movie_name} score"]
    music      = []
    seen       = set()

    for q in queries:
        try:
            r = requests.get(
                "https://itunes.apple.com/search",
                params={"term": q, "media": "music", "entity": "song",
                        "limit": 5, "country": "us"},
                timeout=8,
            )
            if r.status_code != 200:
                continue
            for t in r.json().get("results", []):
                tid = t.get("trackId")
                if not tid or tid in seen:
                    continue
                seen.add(tid)
                artwork = t.get("artworkUrl100",
                                "https://via.placeholder.com/300x300?text=Music")
                artwork = artwork.replace("100x100", "300x300")
                music.append({
                    "title"      : t.get("trackName", "Unknown"),
                    "artist"     : t.get("artistName", "Unknown"),
                    "album"      : t.get("collectionName", ""),
                    "rating"     : round(t.get("trackTimeMillis", 0) / 60000 / 10, 1),
                    "description": f"Recommended for fans of {movie_name}",
                    "image"      : artwork,
                    "preview_url": t.get("previewUrl"),
                    "spotify_url": t.get("trackViewUrl", ""),
                    "source"     : "itunes",
                })
        except Exception as e:
            logger.warning("iTunes query '%s' failed: %s", q, e)

        if len(music) >= 6:
            break

    logger.info("iTunes: returning %d tracks", len(music))
    return music[:6]


# ── book functions ─────────────────────────────────────────────────────────────

def fetch_books(movie_name):
    """Open Library — no API key, no rate limits."""
    query = movie_name.replace(" ", "+")
    try:
        r = requests.get(
            "https://openlibrary.org/search.json",
            params={
                "q"      : query,
                "limit"  : 6,
                "fields" : "key,title,author_name,cover_i,subject,first_publish_year,ratings_average,first_sentence",
            },
            timeout=10,
        )
        r.raise_for_status()
        docs  = r.json().get("docs", [])
        books = []
        seen  = set()

        for doc in docs:
            key = doc.get("key", "")
            if not key or key in seen:
                continue
            seen.add(key)

            cover_id  = doc.get("cover_i")
            thumbnail = (
                f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                if cover_id
                else "https://via.placeholder.com/128x192?text=Book"
            )

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

            if len(books) >= 5:
                break

        logger.info("Books: returning %d results", len(books))
        return books

    except Exception as e:
        logger.error("Open Library error: %s", e)
        return []


# ── routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/auth")
def auth_page():
    return render_template("auth.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "1.0.0",
                    "timestamp": datetime.utcnow().isoformat() + "Z"})


@app.route("/movie-details/<int:movie_id>")
def movie_details_route(movie_id):
    try:
        details = fetch_movie_details(movie_id)
        if not details.get("title"):
            return jsonify({"error": "Movie not found"}), 404
        return jsonify(details)
    except Exception as e:
        logger.error("movie-details error: %s", e)
        return jsonify({"error": "Failed to fetch movie details"}), 500


@app.route("/recommend", methods=["POST"])
def recommend():
    try:
        data  = request.get_json()
        movie = (data or {}).get("movie", "").strip()

        if not movie:
            return jsonify({"error": "Movie title is required"}), 400

        start  = datetime.utcnow()
        logger.info("Recommend: '%s'", movie)

        movies = get_similar_movies(movie)
        music  = get_music_recommendations(movie)
        books  = fetch_books(movie)

        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.info("Done in %.2fs — %d movies, %d music, %d books",
                    elapsed, len(movies), len(music), len(books))

        return jsonify({
            "movies" : movies,
            "music"  : music,
            "books"  : books,
            "meta"   : {
                "query"          : movie,
                "total_results"  : len(movies) + len(music) + len(books),
                "processing_time": f"{elapsed:.2f}s",
            },
        })

    except Exception as e:
        logger.error("Recommend error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# ── entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
