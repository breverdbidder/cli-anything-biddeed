FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --production --quiet
COPY server.js ./
EXPOSE 3100
CMD ["node", "server.js"]
