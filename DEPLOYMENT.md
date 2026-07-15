# Deploy LearnHouse to bbbacademia.com/courses

## ⚠️ Pre-Deployment Security

**CRITICAL: The VPS password was shared in plain text.** Change it immediately:

1. Connect to the VPS via SSH
2. Run: `passwd` and set a strong password
3. **OR** (recommended) switch to SSH key authentication:
   ```bash
   ssh-copy-id -i ~/.ssh/id_rsa ubuntu@51.79.50.184
   # Then disable password auth in /etc/ssh/sshd_config
   ```

---

## Overview

This deployment:
- Mounts LearnHouse at **https://bbbacademia.com/courses** (not a subdomain)
- Runs inside a single Docker container with Next.js + FastAPI + collab server + internal nginx
- Reverse-proxies from aaPanel's **OpenLiteSpeed** (serving bbbacademia.com) to the container on `127.0.0.1:8090`
- Keeps the existing bbbacademia.com site untouched
- Stores data in PostgreSQL + Redis (Docker containers)

---

## Step 1: VPS Preparation

Connect via SSH:
```bash
ssh ubuntu@51.79.50.184
```

### 1a. Install Docker (if not already present)

Check if Docker is installed:
```bash
docker --version
```

If not installed, aaPanel may have a Docker plugin — check the aaPanel admin panel (`:7080`). Or install manually:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
exit  # re-login to apply group
```

### 1b. Create a deployment directory

```bash
mkdir -p ~/learnhouse-courses
cd ~/learnhouse-courses
```

---

## Step 2: Prepare Configuration Files

### 2a. Copy `docker-compose.yml` and `.env.production` to the VPS

**On your local machine**, run:
```bash
scp docker-compose.yml ubuntu@51.79.50.184:~/learnhouse-courses/
scp .env.production ubuntu@51.79.50.184:~/learnhouse-courses/
```

Or manually paste the content via SSH:
```bash
ssh ubuntu@51.79.50.184
cat > ~/learnhouse-courses/docker-compose.yml << 'EOF'
[paste contents of docker-compose.yml]
EOF
```

### 2b. Generate secrets and edit `.env`

On the VPS:
```bash
cd ~/learnhouse-courses

# Copy the template
cp .env.production .env

# Generate secrets (run these and paste the outputs into .env)
openssl rand -hex 32  # for NEXTAUTH_SECRET
openssl rand -hex 32  # for LEARNHOUSE_AUTH_JWT_SECRET_KEY
openssl rand -hex 32  # for COLLAB_INTERNAL_KEY
openssl rand -hex 16  # for DB_PASSWORD
```

Edit `.env` and replace all `<GENERATE: ...>` placeholders with the values you just generated. Also set:
- `LEARNHOUSE_INITIAL_ADMIN_PASSWORD` — a strong password for the initial admin account
- Email provider (optional but recommended) — either Resend or SMTP

**Important**: Save the admin password securely — you'll need it for first login.

---

## Step 3: Clone or Copy the Project Code

### Option A: Git Clone (recommended)

```bash
cd ~/learnhouse-courses
git clone https://github.com/your-org/BBB-Academia.git code
cd code
```

### Option B: Copy from local machine

If you can't use git, SCP the entire repo:
```bash
# On your local machine
scp -r /path/to/BBB-Academia ubuntu@51.79.50.184:~/learnhouse-courses/code
```

**Result**: Your directory structure should be:
```
~/learnhouse-courses/
├── docker-compose.yml
├── .env
└── code/                    # The cloned repo
    ├── Dockerfile
    ├── docker/
    │   ├── nginx.conf
    │   └── start.sh
    └── apps/
```

---

## Step 4: Build and Launch the Container

On the VPS:
```bash
cd ~/learnhouse-courses/code

# Build the Docker image with the /courses basePath
docker build \
  --build-arg NEXT_PUBLIC_BASE_PATH=/courses \
  -t learnhouse-courses:latest \
  .

# Go back to compose directory
cd ..

# Start the services (db, redis, app)
docker compose up -d

# Watch the logs (Ctrl+C to exit)
docker compose logs -f app
```

Expected output:
```
app     | Hocuspocus collab server running on port 4000
app     | Starting LearnHouse backend on 0.0.0.0:9000...
app     | ▲ Next.js 16.2.9
app     | ○ Listening on http://0.0.0.0:8000 (api routes ready)
```

Once you see these, the app is running. Press **Ctrl+C** to exit logs.

---

## Step 5: Configure aaPanel/OpenLiteSpeed Reverse Proxy

Open aaPanel admin panel: **https://your-vps-ip:7080**

1. Log in
2. **WebSite** → **List** → find **bbbacademia.com**
3. Click **Config** (or edit)
4. Find the **Proxy** section (or **Context**)
5. Add a new **Proxy** entry:
   - **URI**: `/courses/` (include trailing slash)
   - **Target**: `http://127.0.0.1:8090/courses/` (loopback + preserve path)
   - **Enable WebSocket** or similar toggle (check your aaPanel version for exact wording)
6. **Save** and **Reload** OpenLiteSpeed

Test via SSH:
```bash
curl http://127.0.0.1:8090/courses/health
# Should return: {"status": "ok"}
```

---

## Step 6: First Boot & Admin Setup

Open your browser to **https://bbbacademia.com/courses**

1. You should see the LearnHouse signup page
2. Sign up with the **initial admin email** from `.env`:
   - Email: `admin@bbbacademia.com`
   - Password: (the one you set in `.env`)
3. Create the **default organization** (name & slug from `.env`)
4. You're logged in! ✓

---

## Step 7: Verify All Features

### 7a. Frontend & static assets
- Visit **https://bbbacademia.com/courses/dash**
- Assets should load (CSS, JS, images under `/courses/_next/static/`)
- No 404 errors in the browser console

### 7b. Authentication flow
- Log out → log back in
- Cookies should set for `.bbbacademia.com` (domain scope)
- No mixed secure/insecure warnings

### 7c. Collaboration (WebSocket)
- Create a new **Board** (from the UI)
- Open two browser tabs at the same board URL
- Edit content in one tab — the other should update in real-time
- Browser DevTools → Network → WS tab should show a connection to `wss://bbbacademia.com/courses/collab`

### 7d. File upload & content delivery
- Create a course with a **media block** or **SCORM package**
- Upload a file
- Verify it's stored and can be downloaded/played
- Content URLs should be under `/courses/content/...`

### 7e. Backend API
- Create a course via the UI (triggers `POST /api/v1/...`)
- Monitor the app logs:
  ```bash
  docker compose logs -f app | grep "POST\|GET"
  ```
- No 502/504 errors in the proxy; api responses should come through

### 7f. Existing site is untouched
- Visit **https://bbbacademia.com** (root)
- Confirm your main site still works normally (NOT affected by the proxy config)

---

## Ongoing Operations

### View logs
```bash
cd ~/learnhouse-courses
docker compose logs -f app
```

### Stop the app
```bash
docker compose down
```

### Restart the app
```bash
docker compose up -d
```

### Update to latest code
```bash
cd ~/learnhouse-courses/code
git pull
docker build --build-arg NEXT_PUBLIC_BASE_PATH=/courses -t learnhouse-courses:latest .
cd ..
docker compose down
docker compose up -d
```

### Backup database
```bash
docker compose exec db pg_dump -U learnhouse learnhouse > backup-$(date +%Y%m%d).sql
```

### Monitor health
```bash
docker compose ps
# or
docker compose logs app | tail -20
```

---

## Troubleshooting

### 1. **502 Bad Gateway** when accessing https://bbbacademia.com/courses

**Check container is running:**
```bash
docker compose ps
# STATUS should be "Up"
```

**Check app is healthy:**
```bash
curl http://127.0.0.1:8090/courses/health
```

**Check logs for errors:**
```bash
docker compose logs app | tail -50
```

### 2. **WebSocket connection fails** (collaboration doesn't work)

**Verify WebSocket proxy is enabled in aaPanel** (check step 5)

**Check collab server is running:**
```bash
docker compose logs app | grep "Hocuspocus"
```

**Test collab endpoint directly:**
```bash
curl -i -N -H "Upgrade: websocket" -H "Connection: Upgrade" \
  http://127.0.0.1:8090/courses/collab 2>&1 | head -10
# Should see upgrade response, not a 404
```

### 3. **Database connection errors**

**Check Postgres is healthy:**
```bash
docker compose exec db psql -U learnhouse -d learnhouse -c "SELECT 1;"
# Should return: 1
```

**Check connection string in `.env`:**
```bash
# Should match the service name in docker-compose.yml:
# postgresql://learnhouse:PASSWORD@db:5432/learnhouse
```

### 4. **Email not sending**

If you configured email in `.env`:
```bash
docker compose logs app | grep -i mail
```

Check credentials are correct and the service isn't rate-limited.

### 5. **Static assets return 404**

**Verify basePath is set correctly in the image:**
```bash
docker compose logs app | grep "basePath"
```

**Check nginx routing:**
```bash
curl -I http://127.0.0.1:8090/courses/_next/static/test
# Should NOT return 404 (at minimum, it redirects or proxies to Next.js)
```

---

## Production Checklist

Before considering this deployment complete:

- [ ] Admin account created and can log in
- [ ] Root site (bbbacademia.com) still works
- [ ] `/courses` loads without 404/502
- [ ] Static assets load (CSS, JS visible in page)
- [ ] Signup flow works end-to-end
- [ ] WebSocket collaboration works (board edits in real-time)
- [ ] File upload works
- [ ] Email notifications work (if configured)
- [ ] Database backups are scheduled
- [ ] SSL certificate is valid (check browser 🔒)
- [ ] Logs are being monitored (set up log rotation if needed)

---

## Next Steps

1. **Monitor logs daily** for errors
2. **Schedule database backups** (cron job or manual)
3. **Plan upgrades** — when new LearnHouse versions are released, merge upstream changes and rebuild the image
4. **Set up SSL certificates** for automatic renewal (aaPanel may handle this automatically for the proxy)
5. **Enable analytics** (Sentry, Logfire) if desired
6. **Configure email provider** if not already done
7. **Invite users** and start building courses!

---

## Support

If you encounter issues:

1. Check logs: `docker compose logs -f app`
2. Verify DNS and SSL: `curl -I https://bbbacademia.com/courses`
3. Test direct container: `curl http://127.0.0.1:8090/courses/`
4. Review this guide's **Troubleshooting** section

For upstream LearnHouse issues, refer to: https://github.com/learnhouse/learnhouse
