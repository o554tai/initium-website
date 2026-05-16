# INITIUM Studio Backend

## What Is This?

A Flask backend that adds **AI video + image generation** to your INITIUM website, with **team permissions** so only authorized members can generate content.

## Architecture

```
├── app.py              # Flask server (static files + API)
├── auth.py             # API key auth system
├── admin.py            # CLI for managing team keys
├── seedance.py         # BytePlus Seedance video integration
├── imagegen.py         # fal.ai image generation integration
├── start.sh            # Startup script (activates venv)
├── keys.json           # Team keys database
├── jobs.json           # Job history
└── static/
    ├── videos/           # Downloaded video files
    └── images/           # Generated image files
```

## API Endpoints

### Team Endpoints (require `X-API-Key` header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate` | Submit video generation task (paid) |
| `POST` | `/api/generate-image` | Submit image generation task (free) |
| `GET`  | `/api/jobs` | List your jobs |
| `GET`  | `/api/jobs/<id>` | Get job status + poll upstream |
| `GET`  | `/api/me` | Check your key info |

### Admin Endpoints (require `X-Admin-Key` header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/admin/keys` | List all team keys |
| `POST` | `/admin/keys` | Create new team key |
| `POST` | `/admin/keys/<key>/revoke` | Revoke a key |
| `DELETE` | `/admin/keys/<key>` | Delete a key |
| `GET`  | `/admin/jobs` | List all jobs |
| `GET`  | `/admin/stats` | Usage statistics |

## Quick Start

### 1. Start the Backend

```bash
cd /home/hermes/initium-website/backend
bash start.sh
```

Server runs on `http://0.0.0.0:5000`

### 2. Get Your Admin Key

```bash
cat keys.json | grep admin_key
```

Or it was printed when you first ran the server.

### 3. Create Team Keys

```bash
# Create a key for Ainsley
python3 admin.py create "Ainsley"

# List all keys
python3 admin.py list

# Revoke a key
python3 admin.py revoke initium-xxxxxxxx...

# Delete a key
python3 admin.py delete initium-xxxxxxxx...
```

### 4. Team Members Use the Studio

1. Open `http://your-server:5000/video-studio.html`
2. Enter their API key
3. Switch between **Video Studio** and **Image Studio** tabs
4. Write prompt → Generate → Download

## Image Generation Setup

Images are generated via **fal.ai** (free for team members, no Stripe required).

1. Sign up at [fal.ai](https://fal.ai)
2. Get your API key from the dashboard
3. Set `FAL_API_KEY` in your environment variables
4. Redeploy

Available models:
- **Flux Pro** ($0.04/image) — best overall quality
- **Flux Ultra** ($0.04/image) — highest detail
- **Seedream V4** ($0.03/image) — BytePlus image model via fal

## Environment Variables

| Variable | Description |
|----------|-------------|
| `INITIUM_ADMIN_KEY` | Override auto-generated admin key |
| `SEEDANCE_API_KEY` | BytePlus Seedance API key for video generation |
| `FAL_API_KEY` | fal.ai API key for image generation |
| `STRIPE_SECRET_KEY` | Stripe secret key for payments |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key for client-side payments |

## Running as a Service (Production)

Create `/etc/systemd/system/initium-studio.service`:

```ini
[Unit]
Description=INITIUM Video Studio
After=network.target

[Service]
Type=simple
User=hermes
WorkingDirectory=/home/hermes/initium-website/backend
ExecStart=/home/hermes/seedance-env/bin/python3 /home/hermes/initium-website/backend/app.py
Restart=always
Environment=INITIUM_ADMIN_KEY=your-secure-admin-key

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable initium-studio
sudo systemctl start initium-studio
```

## Security Notes

- Keep `keys.json` secure — it contains all API keys
- The admin key has full control — store it in env vars, never commit it
- Team keys are bearer tokens — share via secure channels only
- Video files are stored in `static/videos/` — clean up periodically
- Image files are stored in `static/images/` — clean up periodically
