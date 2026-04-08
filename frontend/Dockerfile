FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --legacy-peer-deps
COPY . .

# NEXT_PUBLIC_API_URL is baked into the Next.js bundle at build time.
# Railway MUST set this env variable to your backend service URL before building.
# Example: https://backend-production-xxxx.up.railway.app
# DO NOT default to "" — an empty string causes ALL API calls to hit the frontend itself.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Pass through the API URL so runtime can also read it
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Copy standalone output
RUN mkdir -p ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public 2>/dev/null || true

# Railway assigns PORT dynamically — do NOT hardcode it.
# The Next.js standalone server.js reads process.env.PORT automatically.
EXPOSE 3000
CMD ["node", "server.js"]
