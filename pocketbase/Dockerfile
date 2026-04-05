FROM alpine:3.19

WORKDIR /pb

# Install curl + unzip to download the Linux binary at build time
# (the repo contains a macOS binary — we always fetch the Linux AMD64 version)
RUN apk add --no-cache curl unzip ca-certificates

# Download PocketBase 0.22.20 Linux AMD64
RUN curl -fsSL \
    "https://github.com/pocketbase/pocketbase/releases/download/v0.22.20/pocketbase_0.22.20_linux_amd64.zip" \
    -o /tmp/pb.zip && \
    unzip /tmp/pb.zip -d /pb && \
    chmod +x /pb/pocketbase && \
    rm /tmp/pb.zip

COPY pb_migrations ./pb_migrations

EXPOSE 8090

# Railway sets $PORT dynamically — default to 8090 for local dev
CMD ["sh", "-c", "./pocketbase serve --http=0.0.0.0:${PORT:-8090} --dir=/pb/pb_data"]
