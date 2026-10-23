"""Start FastAPI using the backend-only .env server settings."""
import uvicorn
from .config import Settings

def main():
    settings = Settings.from_env()
    uvicorn.run('app.main:app', host=settings.backend_host, port=settings.backend_port)

if __name__ == '__main__':
    main()
