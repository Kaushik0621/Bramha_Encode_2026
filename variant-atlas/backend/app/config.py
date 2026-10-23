import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]

@dataclass
class Settings:
    backend_host: str = '0.0.0.0'
    backend_port: int = 8000
    frontend_origin: str = 'http://localhost:8500'
    data_backend: str = 'local'
    local_data_dir: Path = ROOT / 'var'
    mongodb_uri: str = field(default='', repr=False)
    mongodb_database: str = 'variant_atlas'
    llm_provider: str = 'mock'
    openrouter_api_key: str = field(default='', repr=False)
    openrouter_model: str = ''
    openrouter_base_url: str = 'https://openrouter.ai/api/v1'
    llm_timeout_seconds: float = 45
    llm_max_output_tokens: int = 1500
    llm_max_steps: int = 6
    cors_origins: tuple[str, ...] = ('http://localhost:8500', 'http://127.0.0.1:8500')

    @classmethod
    def from_env(cls):
        # Process environment wins. Reading files must not mutate os.environ or cause
        # test/CI fixture overrides to invoke a real, configured provider accidentally.
        env = {**dotenv_values(ROOT / '.env'), **dotenv_values(ROOT / 'backend' / '.env'), **os.environ}
        origin = str(env.get('FRONTEND_ORIGIN') or 'http://localhost:8500').rstrip('/')
        parsed = urlsplit(origin)
        origins = [origin]
        if parsed.hostname in ('localhost', '127.0.0.1'):
            alias = '127.0.0.1' if parsed.hostname == 'localhost' else 'localhost'
            port = f':{parsed.port}' if parsed.port else ''
            origins.append(urlunsplit((parsed.scheme, alias + port, '', '', '')))
        explicit = env.get('CORS_ORIGINS')
        if explicit:
            origins = [x.strip().rstrip('/') for x in explicit.split(',') if x.strip()]
        backend_port = int(env.get('BACKEND_PORT') or '8000')
        if not 1 <= backend_port <= 65535:
            raise ValueError('BACKEND_PORT must be between 1 and 65535.')
        return cls(backend_host=str(env.get('BACKEND_HOST') or '0.0.0.0'),
            backend_port=backend_port, frontend_origin=origin,
            data_backend=str(env.get('DATA_BACKEND') or 'local'),
            local_data_dir=Path(env.get('LOCAL_DATA_DIR') or ROOT / 'var'),
            mongodb_uri=str(env.get('MONGODB_URI') or ''),
            mongodb_database=str(env.get('MONGODB_DATABASE') or 'variant_atlas'),
            llm_provider=str(env.get('LLM_PROVIDER') or 'mock'),
            openrouter_api_key=str(env.get('OPENROUTER_API_KEY') or ''),
            openrouter_model=str(env.get('OPENROUTER_MODEL') or ''),
            openrouter_base_url=str(env.get('OPENROUTER_BASE_URL') or 'https://openrouter.ai/api/v1').rstrip('/'),
            llm_timeout_seconds=min(max(float(env.get('LLM_TIMEOUT_SECONDS') or '45'), 1), 120),
            llm_max_output_tokens=min(max(int(env.get('LLM_MAX_OUTPUT_TOKENS') or '1500'), 256), 4000),
            llm_max_steps=min(max(int(env.get('LLM_MAX_STEPS') or '6'), 1), 6),
            cors_origins=tuple(dict.fromkeys(origins)))
