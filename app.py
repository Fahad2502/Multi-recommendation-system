from flask import Flask, render_template, request, jsonify
from rapidfuzz import process
import requests
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv





# Load env variables
load_dotenv()

MOVIES_API_KEY = os.getenv("MOVIES_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")


app = Flask(__name__)

# ---------------- Helper Functions ---------------- #

def best_match(user_input, movie_titles):
    """Return the closest match from movie_titles for user_input using fuzzy matching."""
    match = process.extractOne(user_input, movie_titles)
    return match[0] if match else user_input

def fetch_movie_details(movie_id):
    """Fetch movie details, cast, and trailer from TMDB."""
    movie_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={MOVIES_API_KEY}&language=en-US"
    movie_data = requests.get(movie_url).json()

    # Cast (top 3)
    cast_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={MOVIES_API_KEY}&language=en-US"
    cast_data = requests.get(cast_url).json()
    top_cast = cast_data.get("cast", [])[:3]
    cast_info = [{
        "name": actor["name"],
        "profile": f"https://image.tmdb.org/t/p/w185{actor['profile_path']}" if actor.get("profile_path") else "https://via.placeholder.com/80"
    } for actor in top_cast]

    # Trailer
    video_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={MOVIES_API_KEY}&language=en-US"
    video_data = requests.get(video_url).json()
    trailer_key = next(
        (v["key"] for v in video_data.get("results", []) if v.get("type") == "Trailer" and v.get("site") == "YouTube"),
        None
    )

    return {
        "title": movie_data.get("title"),
        "overview": movie_data.get("overview"),
        "rating": movie_data.get("vote_average"),
        "release": movie_data.get("release_date"),
        "cast": cast_info,
        "trailer": trailer_key
    }

def get_similar_movies(movie_name):
    """Fetch similar and recommended movies from TMDB based on movie_name."""
    search_url = "https://api.themoviedb.org/3/search/movie"
    search_response = requests.get(search_url, params={"api_key": MOVIES_API_KEY, "query": movie_name})
    search_results = search_response.json().get("results", [])

    if not search_results:
        return []

    titles = [m["title"] for m in search_results]
    best_title = best_match(movie_name, titles)
    chosen = next((m for m in search_results if m["title"] == best_title), search_results[0])
    movie_id = chosen["id"]

    movie_data = [{
        "id": chosen["id"],
        "title": chosen["title"],
        "poster": f"https://image.tmdb.org/t/p/w500{chosen['poster_path']}" if chosen.get("poster_path") else None
    }]

    # Recommendations + Similar
    rec_url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
    sim_url = f"https://api.themoviedb.org/3/movie/{movie_id}/similar"

    rec_data = requests.get(rec_url, params={"api_key": MOVIES_API_KEY}).json().get("results", [])
    sim_data = requests.get(sim_url, params={"api_key": MOVIES_API_KEY}).json().get("results", [])

    combined = {m["id"]: m for m in rec_data + sim_data}.values()
    sorted_movies = sorted(combined, key=lambda m: (m.get("vote_average", 0), m.get("popularity", 0)), reverse=True)

    for movie in sorted_movies[:5]:
        movie_data.append({
            "id": movie["id"],
            "title": movie["title"],
            "poster": f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get("poster_path") else None
        })

    return movie_data

def get_music_recommendations(movie_name):
    """Fetch top 5 music tracks related to the movie from Spotify."""
    try:
        sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET
            )
        )
        results = sp.search(q=movie_name, type='track', limit=5)
        tracks = results['tracks']['items']

        music_data = []
        for track in tracks:
            artist = track['artists'][0]
            artist_info = sp.artist(artist['id'])
            music_data.append({
                "title": track['name'],
                "artist": artist['name'],
                "rating": round(track['popularity'] / 20, 1),
                "description": f"A top track inspired by the movie {movie_name}.",
                "image": artist_info['images'][0]['url'] if artist_info['images'] else "https://via.placeholder.com/100"
            })
        return music_data
    except Exception as e:
        print("Error fetching from Spotify:", e)
        return []

def fetch_books(movie_name):
    """Fetch top 5 books related to the movie (no API key needed)."""
    query = f"{movie_name} book"
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}"
    response = requests.get(url)

    books = []
    if response.status_code == 200:
        data = response.json()
        for item in data.get("items", [])[:5]:
            info = item.get("volumeInfo", {})
            books.append({
                "title": info.get("title", "No title"),
                "authors": info.get("authors", ["Unknown Author"]),
                "description": info.get("description", "No description available."),
                "thumbnail": info.get("imageLinks", {}).get("thumbnail", ""),
                "rating": info.get("averageRating", "N/A"),
                "genre": info.get("categories", ["Unknown"])[0]
            })
    return books

# ---------------- Routes ---------------- #

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/movie-details/<int:movie_id>")
def movie_details_route(movie_id):
    details = fetch_movie_details(movie_id)
    return jsonify(details)

@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.get_json()
    movie = data.get("movie")

    movies = get_similar_movies(movie)
    music = get_music_recommendations(movie)
    books = fetch_books(movie)

    return jsonify({
        "movies": movies,
        "music": music,
        "books": books
    })

# ---------------- Run App ---------------- #

if __name__ == '__main__':
    app.run(debug=True)
