FROM alpine:3.19

WORKDIR /pb

# Copy the pre-built PocketBase binary
COPY pocketbase ./pocketbase
COPY pb_migrations ./pb_migrations

RUN chmod +x ./pocketbase

EXPOSE 8090

# pb_data is ephemeral on Railway free tier — attach a volume for persistence
CMD ["./pocketbase", "serve", "--http=0.0.0.0:8090", "--dir=/pb/pb_data"]
