# Deployment Guide

## Production Deployment Options

### Option 1: Docker Deployment (Recommended)

#### Prerequisites
- Docker and Docker Compose installed
- Domain name (optional)
- SSL certificate (optional)

#### Steps

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd ai_DA
```

2. **Set environment variables**

Create `backend/.env`:
```env
DATABASE_URL=postgresql://ai_analyst:STRONG_PASSWORD@postgres:5432/ai_data_analyst
OPENAI_API_KEY=sk-your-production-key
SECRET_KEY=generate-a-long-random-secret-key-here
ENVIRONMENT=production
CORS_ORIGINS=https://yourdomain.com
```

Create `frontend/.env`:
```env
VITE_API_URL=https://api.yourdomain.com
```

3. **Build and run**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

4. **Set up Nginx reverse proxy** (optional)

Create `/etc/nginx/sites-available/ai-analyst`:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Option 2: Cloud Platform Deployment

#### AWS Deployment

**Services Used**:
- EC2 for application server
- RDS for PostgreSQL
- S3 for file storage
- CloudFront for CDN
- Route 53 for DNS

**Steps**:

1. **Launch EC2 instance**
   - Ubuntu 22.04 LTS
   - t3.medium or larger
   - Open ports 80, 443, 8000

2. **Set up RDS PostgreSQL**
   - PostgreSQL 14+
   - db.t3.micro for testing
   - Note connection string

3. **Configure application**
   ```bash
   # SSH into EC2
   ssh -i your-key.pem ubuntu@your-ec2-ip
   
   # Install dependencies
   sudo apt update
   sudo apt install python3-pip nodejs npm postgresql-client
   
   # Clone and setup
   git clone <your-repo>
   cd ai_DA
   ./setup.sh
   
   # Update .env with RDS connection
   ```

4. **Set up systemd services**

Backend service (`/etc/systemd/system/ai-analyst-backend.service`):
```ini
[Unit]
Description=AI Data Analyst Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/ai_DA/backend
Environment="PATH=/home/ubuntu/ai_DA/backend/venv/bin"
ExecStart=/home/ubuntu/ai_DA/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

Frontend service (`/etc/systemd/system/ai-analyst-frontend.service`):
```ini
[Unit]
Description=AI Data Analyst Frontend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/ai_DA/frontend
ExecStart=/usr/bin/npm run preview -- --host 0.0.0.0 --port 5173

[Install]
WantedBy=multi-user.target
```

Enable services:
```bash
sudo systemctl enable ai-analyst-backend
sudo systemctl enable ai-analyst-frontend
sudo systemctl start ai-analyst-backend
sudo systemctl start ai-analyst-frontend
```

#### Azure Deployment

**Services Used**:
- Azure App Service for backend
- Azure Static Web Apps for frontend
- Azure Database for PostgreSQL
- Azure Blob Storage for files

**Steps**:

1. **Create resources**
```bash
az group create --name ai-analyst-rg --location eastus

az postgres flexible-server create \
  --resource-group ai-analyst-rg \
  --name ai-analyst-db \
  --admin-user dbadmin \
  --admin-password YourPassword123!

az webapp create \
  --resource-group ai-analyst-rg \
  --plan ai-analyst-plan \
  --name ai-analyst-backend \
  --runtime "PYTHON:3.11"
```

2. **Deploy backend**
```bash
cd backend
az webapp up --name ai-analyst-backend --resource-group ai-analyst-rg
```

3. **Deploy frontend**
```bash
cd frontend
npm run build
az storage blob upload-batch -d '$web' -s dist --account-name aianalystfrontend
```

#### Google Cloud Platform Deployment

**Services Used**:
- Cloud Run for containers
- Cloud SQL for PostgreSQL
- Cloud Storage for files
- Cloud CDN

**Steps**:

1. **Build containers**
```bash
# Build backend
docker build -t gcr.io/your-project/ai-analyst-backend:latest ./backend

# Build frontend  
docker build -t gcr.io/your-project/ai-analyst-frontend:latest ./frontend

# Push to Container Registry
docker push gcr.io/your-project/ai-analyst-backend:latest
docker push gcr.io/your-project/ai-analyst-frontend:latest
```

2. **Deploy to Cloud Run**
```bash
gcloud run deploy ai-analyst-backend \
  --image gcr.io/your-project/ai-analyst-backend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

gcloud run deploy ai-analyst-frontend \
  --image gcr.io/your-project/ai-analyst-frontend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Option 3: Heroku Deployment

**Steps**:

1. **Create Heroku apps**
```bash
heroku create ai-analyst-backend
heroku create ai-analyst-frontend
```

2. **Add PostgreSQL**
```bash
heroku addons:create heroku-postgresql:mini -a ai-analyst-backend
```

3. **Set environment variables**
```bash
heroku config:set OPENAI_API_KEY=sk-your-key -a ai-analyst-backend
```

4. **Deploy**
```bash
# Backend
cd backend
git init
heroku git:remote -a ai-analyst-backend
git add .
git commit -m "Deploy"
git push heroku main

# Frontend
cd frontend
git init
heroku git:remote -a ai-analyst-frontend
git add .
git commit -m "Deploy"
git push heroku main
```

## Production Checklist

### Security
- [ ] Change all default passwords
- [ ] Generate strong SECRET_KEY
- [ ] Enable HTTPS/SSL
- [ ] Configure CORS properly
- [ ] Set up firewall rules
- [ ] Enable rate limiting
- [ ] Regular security updates

### Performance
- [ ] Enable database connection pooling
- [ ] Configure caching (Redis)
- [ ] Set up CDN for static files
- [ ] Optimize database indexes
- [ ] Enable gzip compression
- [ ] Monitor resource usage

### Reliability
- [ ] Set up automated backups
- [ ] Configure health checks
- [ ] Set up monitoring (Datadog, New Relic)
- [ ] Configure logging (CloudWatch, Stackdriver)
- [ ] Set up error tracking (Sentry)
- [ ] Create disaster recovery plan

### Scalability
- [ ] Configure auto-scaling
- [ ] Set up load balancer
- [ ] Use managed database service
- [ ] Implement job queue for long tasks
- [ ] Configure session storage (Redis)
- [ ] Plan for traffic spikes

## Monitoring

### Backend Health Check
```bash
curl http://your-domain/health
```

### Logs
```bash
# Docker
docker-compose logs -f backend

# Systemd
journalctl -u ai-analyst-backend -f

# Cloud platforms
# AWS CloudWatch, Azure Monitor, GCP Stackdriver
```

### Metrics to Monitor
- API response times
- Database query performance
- Error rates
- Memory usage
- CPU usage
- Disk space
- Active sessions

## Maintenance

### Database Backups
```bash
# Manual backup
pg_dump ai_data_analyst > backup.sql

# Automated daily backups (cron)
0 2 * * * pg_dump ai_data_analyst > /backups/ai_analyst_$(date +\%Y\%m\%d).sql
```

### Updates
```bash
# Pull latest changes
git pull origin main

# Update backend dependencies
cd backend
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Update frontend dependencies
cd frontend
npm update

# Restart services
docker-compose restart
# or
sudo systemctl restart ai-analyst-backend ai-analyst-frontend
```

## Troubleshooting

### Application won't start
- Check logs
- Verify environment variables
- Check database connection
- Verify all dependencies installed

### Performance issues
- Check database queries
- Monitor memory usage
- Review error logs
- Check external API limits (OpenAI)

### Database connection errors
- Verify DATABASE_URL
- Check firewall rules
- Verify database is running
- Check connection limits

## Support

For production support:
- Review logs first
- Check monitoring dashboards
- Verify all services are running
- Contact support with logs and error messages
