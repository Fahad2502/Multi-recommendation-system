"""
Music service — Spotify (primary) with iTunes Search API fallback.

Queries are built from the movie's genre + keywords rather than the raw title,
so results are thematically matched instead of literally named after the film.
"""
import logging
from typing import Optional

import httpx
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from app.core.config import settings

logger = logging.getLogger(__name__)

# Film genre → iTunes search term for the fallback path
_GENRE_TO_TERM: dict[str, str] = {
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


async def get_music_recommendations(ctx: dict) -> list:
    """
    Try Spotify first. If it returns nothing (quota / auth issue),
    fall back to the free iTunes Search API.
    """
    tracks = await _from_spotify(ctx)
    if not tracks:
        logger.info("Spotify unavailable — falling back to iTunes Search API")
        tracks = await _from_itunes(ctx)
    return tracks


# ── Spotify ───────────────────────────────────────────────────────────────────

async def _from_spotify(ctx: dict) -> list:
    """Build genre/keyword queries and hit Spotify search."""
    try:
        sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=settings.spotify_client_id,
                client_secret=settings.spotify_client_secret,
            )
        )

        title    = ctx["title"]
        genres   = ctx["genres"][:2]
        keywords = ctx["keywords"][:3]

        queries = [f"{title} soundtrack", f"{title} score"]
        queries += [f"{g} cinematic score" for g in genres]
        if keywords:
            queries.append(f"{' '.join(keywords[:2])} music")
        if ctx.get("director"):
            queries.append(f"{ctx['director']} film score")

        all_tracks: list[dict] = []
        seen: set[str] = set()

        for q in queries[:5]:
            try:
                res = sp.search(q=q, type="track", limit=10)
                for t in res["tracks"]["items"]:
                    if t["id"] not in seen:
                        seen.add(t["id"])
                        all_tracks.append(t)
            except Exception as exc:
                logger.warning("Spotify query '%s' failed: %s", q, exc)

        if not all_tracks:
            return []

        all_tracks.sort(key=lambda t: t["popularity"], reverse=True)

        results: list[dict] = []
        for track in all_tracks[:settings.max_music]:
            try:
                artist      = track["artists"][0]
                artist_info = sp.artist(artist["id"])
                image       = (
                    artist_info["images"][0]["url"]
                    if artist_info.get("images")
                    else "https://via.placeholder.com/300x300?text=Music"
                )
                results.append({
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
            except Exception as exc:
                logger.warning("Error processing Spotify track: %s", exc)

        return results

    except Exception as exc:
        logger.error("Spotify service error: %s", exc)
        return []


# ── iTunes fallback ───────────────────────────────────────────────────────────

async def _from_itunes(ctx: dict) -> list:
    """
    iTunes Search API — free, no key required.
    Returns 30-second preview MP3 URLs that play directly in the browser.
    """
    title  = ctx["title"]
    genres = ctx["genres"]

    queries = [f"{title} soundtrack", f"{title} score"]
    for g in genres[:2]:
        term = _GENRE_TO_TERM.get(g)
        if term:
            queries.append(term)

    results: list[dict] = []
    seen: set[int] = set()

    async with httpx.AsyncClient() as client:
        for q in queries[:3]:
            try:
                r = await client.get(
                    "https://itunes.apple.com/search",
                    params={"term": q, "media": "music", "entity": "song",
                            "limit": 5, "country": "us"},
                    timeout=8,
                )
                if r.status_code != 200:
                    continue

                for t in r.json().get("results", []):
                    track_id: Optional[int] = t.get("trackId")
                    if not track_id or track_id in seen:
                        continue
                    seen.add(track_id)

                    artwork = t.get("artworkUrl100",
                                    "https://via.placeholder.com/300x300?text=Music")
                    artwork = artwork.replace("100x100", "300x300")

                    results.append({
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

            except Exception as exc:
                logger.warning("iTunes query '%s' failed: %s", q, exc)

            if len(results) >= settings.max_music:
                break

    return results[:settings.max_music]
