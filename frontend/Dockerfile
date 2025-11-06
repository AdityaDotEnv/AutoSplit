# frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

ENV CI=true
# Vite dev server:
ENV HOST=0.0.0.0
ENV PORT=5173
ENV CHOKIDAR_USEPOLLING=true

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# If "npm start" runs vite, pass host/port flags so it works in Docker
CMD ["npm", "start", "--", "--host", "0.0.0.0", "--port", "5173"]
