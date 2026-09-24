FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --fetch-retries=5 --fetch-retry-maxtimeout=120000

COPY . .

# Vite bakes these into the bundle at build time — the app runs in the visitor's
# browser, so the API URL has to be one *the browser* can reach, not a Docker-internal hostname.
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_WALKTHROUGH_VIDEO_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_WALKTHROUGH_VIDEO_URL=$VITE_WALKTHROUGH_VIDEO_URL

RUN npm run build


FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
