"""
All Pydantic schemas for the recommendations API.

Keeping schemas in one file makes them easy to browse and reuse across routes.
"""
from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator


# ── Requests ──────────────────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    movie: str = Field(..., min_length=1, max_length=200, examples=["Inception"])

    @field_validator("movie")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("movie title cannot be blank")
        return stripped


# ── Movie schemas ─────────────────────────────────────────────────────────────

class MovieCard(BaseModel):
    """One movie card shown in the results grid."""
    id: int
    title: str
    poster: str
    release_date: str
    rating: float
    overview: str


class CastMember(BaseModel):
    name: str
    profile: str


class MovieDetailResponse(BaseModel):
    """Full detail modal response."""
    title: Optional[str]
    overview: Optional[str]
    rating: Optional[float]
    release: Optional[str]
    genres: List[str]
    runtime: Optional[int]
    cast: List[CastMember]
    trailer: Optional[str]  # YouTube video key, e.g. "YoHD9XEInc0"


# ── Music schemas ─────────────────────────────────────────────────────────────

class MusicCard(BaseModel):
    """One music track card."""
    title: str
    artist: str
    album: str
    rating: float
    description: str
    image: str
    preview_url: Optional[str] = None  # 30-second MP3 preview
    spotify_url: str
    source: str = Field(..., description="'spotify' or 'itunes'")


# ── Book schemas ──────────────────────────────────────────────────────────────

class BookCard(BaseModel):
    """One book card."""
    title: str
    authors: List[str]
    description: str
    thumbnail: str
    rating: Union[float, str]   # "N/A" when Open Library has no rating
    genre: str
    year: Union[int, str]


# ── Recommend response ────────────────────────────────────────────────────────

class RecommendContext(BaseModel):
    """Semantic context extracted from TMDB — shown to the user as tags."""
    matched_title: str
    genres: List[str]
    keywords: List[str]


class RecommendMeta(BaseModel):
    query: str
    total_results: int
    processing_time: str
    cached: bool


class RecommendResponse(BaseModel):
    movies: List[MovieCard]
    music: List[MusicCard]
    books: List[BookCard]
    context: RecommendContext
    meta: RecommendMeta


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
