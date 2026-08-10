FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY mundo ./mundo
COPY avaliador ./avaliador
COPY integridade ./integridade
COPY centrais ./centrais

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "avaliador.cli", "--help"]
