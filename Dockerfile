FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
RUN pip install --upgrade pip && pip install .

COPY scripts /app/scripts
RUN chmod +x /app/scripts/*.sh

EXPOSE 8000
CMD ["uvicorn", "lean_report_card.main:app", "--host", "0.0.0.0", "--port", "8000"]
