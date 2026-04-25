# ---------------------------------------------------------------------------
# Stage 1 – builder: installa le dipendenze Python in un venv isolato
# ---------------------------------------------------------------------------
FROM python:3.10-slim AS builder

# Dipendenze di sistema necessarie per compilazione/runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libglib2.0-0 \
        libgomp1 \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install

# Copia solo il file requirements per sfruttare la cache layer
COPY ocr_project/requirements.txt .

RUN pip install --upgrade pip \
 && pip install --prefix=/install/pkg --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 – runtime: immagine finale leggera
# ---------------------------------------------------------------------------
FROM python:3.10-slim AS runtime

# Dipendenze di sistema runtime (no compilatori)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copia i pacchetti Python installati dallo stage builder
COPY --from=builder /install/pkg /usr/local

WORKDIR /app

# Copia il codice sorgente del progetto
COPY ocr_project/ .

# Crea le cartelle di supporto runtime
RUN mkdir -p data/uploads data/output data/input

# Non eseguire mai come root
RUN adduser --disabled-password --gecos "" appuser \
 && chown -R appuser:appuser /app
USER appuser

# Espone la porta dell'applicazione Flask
EXPOSE 9894

# Variabili d'ambiente sensibili al runtime
ENV FLASK_APP=app.py \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Avvia il server Flask sulla porta 9894
CMD ["python", "app.py"]
