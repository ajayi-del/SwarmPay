FROM python:3.11-slim

WORKDIR /app

# Build tools: gcc/g++ for native extensions; curl + rustup for solders if no wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl nodejs npm && \
    curl https://sh.rustup.rs -sSf | sh -s -- -y --profile minimal && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install Lit Protocol js requirements for the orchestrator
RUN cd contracts && npm install

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
