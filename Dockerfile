FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
# Landing page and architecture page served by src/bank_officer/main.py
COPY index.html bank-officer-agent-architecture-hu.html ./

EXPOSE 8050

CMD ["uv", "run", "--no-dev", "python", "src/bank_officer/main.py"]
