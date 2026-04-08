FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --legacy-peer-deps
COPY . .

# NEXT_PUBLIC_API_URL must be set at BUILD TIME for Next.js to inline it.
# Railway sets env vars before build, so this will pick it up automatically.
# Fallback to empty string so the app doesn't hardcode localhost in production.
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Copy standalone output
RUN mkdir -p ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public 2>/dev/null || true

EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
