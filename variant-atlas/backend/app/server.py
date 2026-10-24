"""Start FastAPI using the backend-only .env server settings."""
import uvicorn
from .config import Settings

def main():
    settings = Settings.from_env()
    if settings.app_profile=='local' and settings.backend_host not in ('127.0.0.1','localhost','::1'):
        raise ValueError('APP_PROFILE=local requires a loopback BACKEND_HOST. Deployments require authentication and workspace isolation.')
    uvicorn.run('app.main:app', host=settings.backend_host, port=settings.backend_port)

if __name__ == '__main__':
    main()
