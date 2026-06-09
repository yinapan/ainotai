FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY config/ config/
COPY cli.py .

RUN mkdir -p /app/reports

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
ENV HF_DATASETS_OFFLINE=1
ENV NO_PROXY=*
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "cli.py"]
CMD ["--help"]


FROM base AS offline

COPY models/ models/
COPY tools/ tools/

ENTRYPOINT ["python", "cli.py"]
CMD ["scan", "/app/input", "--offline", "--output", "/app/reports"]
