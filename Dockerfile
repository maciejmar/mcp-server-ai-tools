# FROM python:3.12-slim  # Docker Hub — niedostępne w sieci BGK
FROM repo.bank.com.pl/zrai-docker-remote-dev/python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf \
    pip install \
    --trusted-host repo.bank.com.pl \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

CMD ["python", "-m", "src.server"]
