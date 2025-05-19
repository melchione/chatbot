FROM node:20-alpine as base
WORKDIR /app
COPY package*.json ./

RUN npm install && npm ls vite

FROM base as development
ENV NODE_ENV=development

# Copier les fichiers du projet
COPY . .

EXPOSE 8080
ENTRYPOINT ["npm", "run", "dev","--inspect=0.0.0.0:9229"]

FROM base as build
WORKDIR /app

# Copier les fichiers du projet
COPY . .

# Construire le projet
RUN npm run build

FROM node:20-alpine as production
WORKDIR /app

# Copier le build à partir de la phase de build
COPY --from=build /app .

EXPOSE 8080
ENV PORT=8080
ENV HOST=0.0.0.0
ENV NODE_ENV=production
ENV ENVIRONMENT_MODE=production

ENTRYPOINT ["node", "build"]
