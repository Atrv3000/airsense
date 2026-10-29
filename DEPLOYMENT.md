# AirSense Mumbai — Production Deployment Guide

This guide covers deployment options for the **AirSense Mumbai** multi-tier application stack.

---

## 1. Environment & Security Configuration

Before running AirSense in production, copy `.env.example` to `.env` and configure all required secrets:

```bash
# Core Django & Security
DEBUG=False
SECRET_KEY=generate-a-strong-random-50-character-secret-key-here
ALLOWED_HOSTS=api.airsense.yourdomain.com,127.0.0.1,localhost
CORS_ALLOWED_ORIGINS=https://airsense.yourdomain.com,http://localhost:19006,http://localhost:8081

# PostgreSQL Database
DB_NAME=airsense_db
DB_USER=airsense_user
DB_PASSWORD=strong-production-database-password
DB_HOST=db
DB_PORT=5432

# External API Keys & Authentication
OPENAQ_API_KEY=your_openaq_v3_api_key
OPENAQ_API_BASE=https://api.openaq.org/v3
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1/forecast
INGESTION_SECRET_KEY=strong-ingestion-webhook-secret-token

# Rate Throttling
DRF_THROTTLE_ANON=120/min
DRF_THROTTLE_USER=600/min
```

> [!IMPORTANT]
> When `DEBUG=False`, Django will halt with an `ImproperlyConfigured` exception if `SECRET_KEY`, `DB_PASSWORD`, `ALLOWED_HOSTS`, or `INGESTION_SECRET_KEY` are unset.

---

## 2. Containerized Deployment (Recommended: Docker & Docker Compose)

The repository provides a multi-container architecture in `docker-compose.yml`:
- **`db`**: PostgreSQL 16 Alpine with persistent volume `postgres_data`.
- **`backend`**: Gunicorn WSGI Python application server running migrations and serving the REST API.
- **`scheduler`**: Automated background daemon running `python manage.py run_scheduler --interval 3600` for continuous ingestion, forecast precomputation, forecast verification, and alert push dispatching.

### Deploying with Docker:
```bash
# 1. Build and start containers in detached mode
docker-compose up --build -d

# 2. Check container status
docker-compose ps

# 3. View live logs
docker-compose logs -f backend
docker-compose logs -f scheduler
```

---

## 3. Host-Level Production Run (WSGI Gunicorn)

For standalone Linux/macOS/Windows servers without Docker:

```bash
# 1. Activate Python virtual environment
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# 2. Install dependencies & run database migrations
cd backend
pip install -r requirements.txt
python manage.py migrate

# 3. Collect static files
python manage.py collectstatic --noinput

# 4. Start Gunicorn WSGI HTTP Server (Production)
gunicorn airsense_backend.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 3 \
  --threads 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

---

## 4. Background Automated Scheduling

AirSense requires periodic tasks (data ingestion, ML forecasting, accuracy monitoring, alert push delivery). 

### Option A: AirSense Dedicated Scheduler (Recommended)
Run the built-in scheduler as a managed systemd service or Docker daemon:
```bash
python manage.py run_scheduler --interval 3600
```
This runs the full 4-step pipeline every hour:
1. `ingest_air_data`: Fetches real-time CAAQMS/sensor observations and weather data.
2. `precompute_forecasts`: Generates multi-horizon ML predictions (+1h, +3h, +6h, +12h, +24h).
3. `verify_forecasts --days 7`: Compares past predictions with actual readings to track rolling MAE/RMSE.
4. `generate_alerts`: Evaluates CPCB thresholds and dispatches push notifications via Expo Push API.

### Option B: Crontab Setup
Alternatively, configure system cron jobs:
```cron
# Every hour at minute 0: Ingest, Forecast, Verify, and Alert
0 * * * * cd /opt/airsense/backend && /opt/airsense/.venv/bin/python manage.py run_scheduler --once >> /var/log/airsense_cron.log 2>&1

# Weekly on Sunday at 02:00: Retrain ML models on updated measurements
0 2 * * 0 cd /opt/airsense/backend && /opt/airsense/.venv/bin/python manage.py train_models --retrain >> /var/log/airsense_train.log 2>&1
```

---

## 5. Reverse Proxy Configuration (Nginx)

```nginx
server {
    listen 80;
    server_name api.airsense.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/airsense/backend/staticfiles/;
    }

    location /media/ {
        alias /opt/airsense/backend/media/;
    }
}
```

---

## 6. Mobile App Production Build (Expo React Native)

Set `EXPO_PUBLIC_API_URL` to point to your production API endpoint before building:

```bash
cd airsense_mobile

# 1. Set environment variable
export EXPO_PUBLIC_API_URL="https://api.airsense.yourdomain.com"

# 2. Build standalone Android APK / iOS Bundle via Expo EAS
eas build -p android --profile production
```
