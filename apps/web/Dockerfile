FROM node:20-alpine AS deps
WORKDIR /srv/web
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /srv/web
COPY --from=deps /srv/web/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /srv/web
ENV NODE_ENV=production
COPY --from=builder /srv/web/.next/standalone ./
COPY --from=builder /srv/web/.next/static ./.next/static
COPY --from=builder /srv/web/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
