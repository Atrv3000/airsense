# AirSense — Production Deployment Guide

This guide covers deployment options for the **AirSense Mumbai** application stack.

---

## 1. Quick Local Production Run (Windows / Developer Machine)

To run the backend ready for mobile app consumption on your local network:

```powershell
# 1. Activate Virtual Environment
cd c:\Users\bawge\Desktop\airsense
.\.venv\Scripts\Activate.ps1

# 2. Run Database Migrations
cd backend
python manage.py migrate

# 3. Collect Static Files (if serving via web server)
python manage.py collectstatic --noinput

# 4. Start Server on all network interfaces
python manage.py runserver 0.0.0.0:8000
```

---

## 2. Containerized Deployment (Docker & Docker Compose)

The project includes a ready-to-run multi-container setup containing:
- **`db`**: PostgreSQL container with persistent volume storage (`postgres_data`).
- **`backend`**: Gunicorn WSGI Python 3.13 application server with automated migration and station seeding.

### To start with Docker:
```bash
# In the root repository directory
docker-compose up --build -d

# Check running status
docker-compose ps

# View backend logs
docker-compose logs -f backend
```

---

## 3. Production Cloud Deployment (AWS EC2 / DigitalOcean / Render)

### Architecture
```
[ Mobile App (Expo) / Web Users ]
               │
               ▼
   [ Nginx Reverse Proxy (SSL/HTTPS) ]
               │
               ▼
   [ Gunicorn WSGI Server (3 workers) ]
               │
               ▼
      [ Django API Engine ]
         ├── ML Engine (Joblib Model)
         ├── Spatial GIS (IDW NumPy)
         └── PostgreSQL 16+ Database
```

### Recommended Nginx Virtual Host:
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
        alias /app/backend/staticfiles/;
    }
}
```

---

## 4. Mobile App Production Build (Expo EAS)

To build a standalone production APK / Android bundle for smartphones:

```bash
cd airsense_mobile

# 1. Install EAS CLI globally
npm install -g eas-cli

# 2. Login to your Expo account
eas login

# 3. Configure EAS Build
eas build:configure

# 4. Build Android standalone APK
eas build -p android --profile preview
```
