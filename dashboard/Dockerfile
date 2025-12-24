FROM nginx:alpine

# Security: Remove default nginx content
RUN rm -rf /usr/share/nginx/html/*

# Copy dashboard files
COPY src/ /usr/share/nginx/html/

# Custom nginx config for SPA
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location /health { \
        return 200 "healthy"; \
        add_header Content-Type text/plain; \
    } \
    location /ready { \
        return 200 "ready"; \
        add_header Content-Type text/plain; \
    } \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

