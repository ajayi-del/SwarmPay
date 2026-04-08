FROM python:3.11-slim

WORKDIR /app

# Build tools: gcc/g++ for native extensions; curl for downloads
# Install Node.js 18.x from NodeSource (Debian packages are too old for Lit Protocol)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl ca-certificates gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install Lit Protocol JS dependencies (skip optional deps to avoid native build failures)
RUN cd contracts && npm install --omit=optional 2>/dev/null || echo "WARN: npm install had warnings (non-fatal)"

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
