from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # Jira
    JIRA_URL: str = "https://jira.bank.com.pl"
    JIRA_PAT: str = ""

    # Confluence
    CONFLUENCE_URL: str = "https://confluence.bank.com.pl"
    CONFLUENCE_PAT: str = ""

    # Grafana
    GRAFANA_URL: str = "http://grafana.internal:3000"
    GRAFANA_TOKEN: str = ""

    # Bitbucket
    BITBUCKET_URL: str = "https://bitbucket.bank.com.pl"
    BITBUCKET_PAT: str = ""

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"

    # Server
    MCP_SERVER_PORT: int = 8000
    MCP_LOG_LEVEL: str = "INFO"
    MCP_API_KEY: str = ""
    MCP_ALLOWED_LOG_PATHS: str = ""
    MCP_MAX_LOG_LINES: int = 500
    MCP_MAX_LOG_LINES_HARD_LIMIT: int = 2000

    # TLS
    TLS_CA_BUNDLE: str = "/etc/pki/tls/certs/ca-bundle.crt"

    # HTTP timeouts (seconds)
    JIRA_TIMEOUT: float = 30.0
    CONFLUENCE_TIMEOUT: float = 30.0
    GRAFANA_TIMEOUT: float = 60.0
    BITBUCKET_TIMEOUT: float = 30.0
    OLLAMA_TIMEOUT: float = 30.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
