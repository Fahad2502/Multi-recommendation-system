# RecoHub Deployment Guide

## Local Development

### Prerequisites
- Python 3.8+
- pip package manager
- Git

### Setup
```bash
# Clone repository
git clone <repository-url>
cd recohub

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python src/app.py
```

## Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "src.app:app"]
```

### Heroku Deployment
1. Create `Procfile`:
```
web: gunicorn src.app:app
```

2. Deploy:
```bash
heroku create your-app-name
git push heroku main
```

### AWS Deployment
Use AWS Elastic Beanstalk or EC2 with the following configuration:
- Python 3.9 platform
- Environment variables for API keys
- Load balancer for high availability

### Environment Variables
```bash
MOVIES_API_KEY=your_tmdb_key
SPOTIFY_CLIENT_ID=your_spotify_id
SPOTIFY_CLIENT_SECRET=your_spotify_secret
DEBUG=False
LOG_LEVEL=WARNING
```

## Performance Optimization

### Caching
- File-based caching implemented
- Redis can be added for distributed caching
- CDN for static assets

### Monitoring
- Application logs in `logs/recohub.log`
- Health check endpoint at `/health`
- Performance metrics available

### Scaling
- Horizontal scaling supported
- Database can be added for user data
- API rate limiting recommended