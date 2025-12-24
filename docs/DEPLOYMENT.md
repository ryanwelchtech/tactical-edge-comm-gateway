# Backend Deployment Guide

> **Note:** This guide is for deploying backend services to cloud platforms. The dashboard is designed to run locally via Docker Compose for demonstration purposes.

This guide covers options for deploying the TacEdge Gateway backend services to various cloud platforms.

## Overview

The dashboard requires the following backend services:
- **gateway-core** (Port 5000) - Main API gateway
- **crypto-service** (Port 5001) - Encryption service
- **audit-service** (Port 5002) - Audit logging
- **store-forward** (Port 5003) - Message queuing
- **redis** (Port 6379) - Message queue storage

## Option 1: Railway (Recommended for Quick Setup)

Railway provides easy Docker Compose deployment with automatic HTTPS.

### Steps:

1. **Sign up at [Railway](https://railway.app)**

2. **Create a New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your repository

3. **Configure Services**
   - Railway will detect `docker-compose.yml`
   - Add environment variables if needed:
     ```bash
     JWT_SECRET=your-secret-key-here
     REDIS_URL=redis://redis:6379
     ```

4. **Update Dashboard API URL**
   - Railway provides HTTPS URLs for each service
   - Update `dashboard/src/app.js` to point to your Railway URLs:
     ```javascript
     const API_BASE_URL = 'https://your-gateway-service.railway.app';
     ```

5. **Redeploy Dashboard**
   - Push changes to trigger GitHub Pages rebuild
   - Or manually rebuild via GitHub Actions

## Option 2: Render

Render offers free tier with Docker support.

### Steps:

1. **Sign up at [Render](https://render.com)**

2. **Create Web Services**
   - For each service (gateway-core, crypto-service, audit-service, store-forward):
     - New → Web Service
     - Connect GitHub repo
     - Set Dockerfile path: `services/{service-name}/Dockerfile`
     - Set root directory: `services/{service-name}`
     - Add environment variables

3. **Create Redis Service**
   - New → Redis
   - Use the provided Redis URL in your services

4. **Update Service URLs**
   - Render provides HTTPS URLs
   - Update dashboard `app.js` with Render URLs

## Option 3: Fly.io

Fly.io offers global edge deployment.

### Steps:

1. **Install Fly CLI**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login and Create Apps**
   ```bash
   fly auth login
   fly apps create tacedge-gateway
   fly apps create tacedge-crypto
   fly apps create tacedge-audit
   fly apps create tacedge-store-forward
   fly redis create
   ```

3. **Deploy Services**
   - Create `fly.toml` for each service
   - Deploy: `fly deploy`

4. **Configure Networking**
   - Use Fly.io's private networking for inter-service communication
   - Expose gateway-core publicly

## Option 4: Docker Compose on VPS

Deploy to any VPS provider (DigitalOcean, Linode, AWS EC2, etc.).

### Steps:

1. **Provision VPS**
   - Minimum: 2GB RAM, 2 CPU cores
   - Ubuntu 22.04 LTS recommended

2. **Install Docker**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

3. **Install Docker Compose**
   ```bash
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

4. **Clone Repository**
   ```bash
   git clone https://github.com/ryanwelchtech/tactical-edge-comm-gateway.git
   cd tactical-edge-comm-gateway
   ```

5. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

6. **Start Services**
   ```bash
   docker-compose up -d
   ```

7. **Set Up Reverse Proxy (Nginx)**
   ```nginx
   server {
       listen 80;
       server_name api.yourdomain.com;

       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

8. **Set Up SSL (Let's Encrypt)**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d api.yourdomain.com
   ```

9. **Update Dashboard**
   - Update `dashboard/src/app.js` with your domain:
     ```javascript
     const API_BASE_URL = 'https://api.yourdomain.com';
     ```

## Option 5: Kubernetes (Production)

For production deployments, use Kubernetes.

### Steps:

1. **Set up Kubernetes Cluster**
   - Use managed services: GKE, EKS, AKS
   - Or use minikube for local testing

2. **Deploy Services**
   ```bash
   kubectl apply -f deploy/k8s/base/
   ```

3. **Configure Ingress**
   - Set up ingress controller (nginx, traefik)
   - Configure TLS certificates

4. **Update Dashboard**
   - Point to your Kubernetes ingress URL

## CORS Configuration

After deploying, you must configure CORS on the gateway-core service to allow requests from GitHub Pages.

### Update `services/gateway-core/src/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ryanwelchtech.github.io",
        "http://localhost:8081",  # For local testing
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Environment Variables

Create a `.env` file or set these in your deployment platform:

```bash
# JWT Configuration
JWT_SECRET=your-very-secure-secret-key-min-32-chars
JWT_ALGORITHM=HS256

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Service URLs (for inter-service communication)
GATEWAY_URL=http://gateway-core:5000
CRYPTO_SERVICE_URL=http://crypto-service:5001
AUDIT_SERVICE_URL=http://audit-service:5002
STORE_FORWARD_URL=http://store-forward:5003
```

## Testing the Deployment

1. **Check Service Health**
   ```bash
   curl https://your-api-url/health
   ```

2. **Test API Endpoints**
   ```bash
   # Get nodes
   curl https://your-api-url/api/v1/nodes
   
   # Generate token
   curl -X POST https://your-api-url/api/v1/auth/token
   ```

3. **Update Dashboard**
   - Ensure `dashboard/src/app.js` has correct API URL
   - Test dashboard functionality

## Monitoring

Consider adding monitoring:
- **Health Checks**: All services expose `/health` endpoints
- **Logging**: Use centralized logging (Loki, ELK stack)
- **Metrics**: Prometheus + Grafana
- **Uptime Monitoring**: UptimeRobot, Pingdom

## Security Considerations

1. **Use HTTPS**: Always use HTTPS in production
2. **Rotate Secrets**: Regularly rotate JWT_SECRET
3. **Rate Limiting**: Implement rate limiting on public endpoints
4. **Firewall Rules**: Restrict access to internal services
5. **Regular Updates**: Keep dependencies updated

## Cost Estimates

- **Railway**: ~$5-20/month (pay-as-you-go)
- **Render**: Free tier available, ~$7-25/month for production
- **Fly.io**: ~$3-15/month (pay-as-you-go)
- **VPS (DigitalOcean)**: ~$6-12/month (basic droplet)
- **Kubernetes (GKE/EKS)**: ~$25-100+/month (managed)

## Troubleshooting

### Services Not Starting
- Check logs: `docker-compose logs [service-name]`
- Verify environment variables
- Check port availability

### CORS Errors
- Verify CORS configuration in gateway-core
- Check allowed origins match your GitHub Pages URL

### Connection Timeouts
- Verify firewall rules
- Check service health endpoints
- Verify DNS resolution

### Redis Connection Issues
- Ensure Redis is running and accessible
- Check REDIS_HOST and REDIS_PORT settings

## Next Steps

1. Choose a deployment option
2. Deploy backend services
3. Update dashboard API URL
4. Test end-to-end functionality
5. Monitor and maintain

For questions or issues, open an issue on GitHub.

