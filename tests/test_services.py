"""
Unit tests for RecoHub services
"""
import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services import MovieService, MusicService, BookService

class TestMovieService(unittest.TestCase):
    """Test cases for MovieService"""
    
    def setUp(self):
        self.movie_service = MovieService()
    
    @patch('requests.get')
    def test_search_movies_success(self, mock_get):
        """Test successful movie search"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 27205,
                    "title": "Inception",
                    "poster_path": "/test.jpg",
                    "release_date": "2010-07-16",
                    "vote_average": 8.8,
                    "overview": "A thief who steals corporate secrets..."
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Test
        results = self.movie_service.search_movies("Inception")
        
        # Assertions
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Inception")
        self.assertEqual(results[0]["id"], 27205)
    
    @patch('requests.get')
    def test_search_movies_no_results(self, mock_get):
        """Test movie search with no results"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response
        
        results = self.movie_service.search_movies("NonexistentMovie")
        self.assertEqual(len(results), 0)

class TestMusicService(unittest.TestCase):
    """Test cases for MusicService"""
    
    def setUp(self):
        self.music_service = MusicService()
    
    @patch('spotipy.Spotify')
    def test_search_music_success(self, mock_spotify):
        """Test successful music search"""
        # Mock Spotify client
        mock_client = Mock()
        mock_client.search.return_value = {
            "tracks": {
                "items": [
                    {
                        "id": "test_id",
                        "name": "Time",
                        "artists": [{"name": "Hans Zimmer", "id": "artist_id"}],
                        "album": {"name": "Inception Soundtrack"},
                        "popularity": 80,
                        "external_urls": {"spotify": "https://spotify.com/track/test"}
                    }
                ]
            }
        }
        mock_client.artist.return_value = {
            "images": [{"url": "https://example.com/image.jpg"}]
        }
        mock_spotify.return_value = mock_client
        
        # Test
        results = self.music_service.search_music("Inception")
        
        # Assertions
        self.assertGreater(len(results), 0)

class TestBookService(unittest.TestCase):
    """Test cases for BookService"""
    
    def setUp(self):
        self.book_service = BookService()
    
    @patch('requests.get')
    def test_search_books_success(self, mock_get):
        """Test successful book search"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "book_id",
                    "volumeInfo": {
                        "title": "Inception: The Book",
                        "authors": ["Christopher Nolan"],
                        "description": "A book about dreams...",
                        "categories": ["Fiction"],
                        "imageLinks": {"thumbnail": "https://example.com/book.jpg"},
                        "averageRating": 4.5
                    }
                }
            ]
        }
        mock_get.return_value = mock_response
        
        results = self.book_service.search_books("Inception")
        
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["title"], "Inception: The Book")

if __name__ == '__main__':
    unittest.main()