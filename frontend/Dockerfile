# Optional image for CI/production deploy — local dev uses `npm run dev` (see README).
# Production build: docs/runbooks/fly-io-deploy.md (Dockerfile.prod).
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
