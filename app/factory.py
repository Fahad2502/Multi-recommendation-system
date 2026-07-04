"""
Application factory.

Keeps main.py to a single import + call so the app is easy to test
and easy to swap out (different config, lifespan events, middleware, etc.).
"""
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routes import pages, recommendations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_title,
        description=(
            "Cross-domain recommendation engine — enter a movie title and get "
            "semantically matched movies, music, and books. "
            "Powered by TMDB · Spotify / iTunes · Open Library."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Routers
    app.include_router(pages.router)
    app.include_router(recommendations.router)

    return app
