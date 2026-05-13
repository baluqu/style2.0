# StyleBridge Production Deployment Guide

## Overview

StyleBridge is a full-stack Flask application designed for production deployment on Render with PostgreSQL. This guide covers all necessary steps to deploy a secure, scalable instance.

## Pre-Deployment Checklist

### 1. Generate Secure Secrets

Before deployment, generate strong cryptographic secrets:

```bash
# Generate SECRET_KEY (32+ random characters)
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate ADMIN_KEY (32+ random characters)
python -c "import secrets; print('ADMIN_KEY=' + secrets.token_urlsafe(32))"
```

Save these values - you'll need them in the next step.

### 2. Prepare Environment Variables

Copy `.env.example` to create your production `.env`:

```bash
cp .env.example .env
```

Update `.env` with:
- **FLASK_ENV=production**
- **SECRET_KEY** (from step 1, 32+ chars)
- **ADMIN_KEY** (from step 1, 32+ chars)
- **DATABASE_URL** (PostgreSQL connection string from Render)
- **ADMIN_EMAIL** (your admin account email)
- **ADMIN_PASSWORD** (strong password, 12+ chars)

**IMPORTANT:** `.env` is never committed to git. It's git-ignored by default.

### 3. Database Requirements

StyleBridge **requires PostgreSQL** in production. SQLite is not supported.

- Minimum: 1 GB storage
- Connection string format: `postgresql://user:password@host:port/database`

## Deployment on Render

### Step 1: Create PostgreSQL Database on Render

1. Go to [render.com](https://render.com) and create an account
2. Create a new PostgreSQL database:
   - Region: Choose closest to your users
   - PostgreSQL Version: 14 or later
   - Instance Type: Standard (Starter tier for MVP)
3. Copy the **Database URL** - you'll need this for `DATABASE_URL`

### Step 2: Create Web Service on Render

1. In Render dashboard, click **New → Web Service**
2. Connect your GitHub repository
3. Configure the service:

   **Build & Deploy**
   - Build Command: `pip install -r requirements.txt && flask db upgrade`
   - Start Command: `gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 30 wsgi:app`

   **Environment Variables**
   - Add all variables from your `.env` file
   - Critical variables:
     - `FLASK_ENV=production`
     - `SECRET_KEY=` (your generated key)
     - `ADMIN_KEY=` (your generated key)
     - `DATABASE_URL=` (PostgreSQL connection)
     - `FORCE_HTTPS=true`
     - `TRUST_PROXY_HEADERS=true`

   **Deployment**
   - Instance Type: Starter (minimum recommended)
   - Region: Same as your database

4. Click **Create Web Service**
5. Monitor the build logs - deployment takes 2-5 minutes

### Step 3: Connect Database to Web Service

1. In Render dashboard, open your database
2. Copy the **Database URL**
3. Go to Web Service settings → Environment
4. Add: `DATABASE_URL=` (paste the URL from step 2)
5. Redeploy web service

### Step 4: Access Your Deployment

- Your app will be available at: `https://your-service-name.onrender.com`
- Admin panel: `https://your-service-name.onrender.com/admin`
- Login with ADMIN_EMAIL and ADMIN_PASSWORD from `.env`

## Security Verification

After deployment, verify security settings:

```bash
# Check HTTPS enforcement
curl -i https://your-service-name.onrender.com

# Verify security headers
curl -i -H "Accept: text/html" https://your-service-name.onrender.com | grep -i "Strict-Transport-Security\|Content-Security-Policy"

# Check that admin routes are protected
curl -X POST https://your-service-name.onrender.com/admin/grant -d "email=test@test.com&role=user"
# Should return 403 Unauthorized without proper auth
```

## Monitoring & Troubleshooting

### View Logs

In Render dashboard:
1. Open your Web Service
2. Go to **Logs** tab
3. Look for application startup messages

### Common Issues

**Issue: "SECRET_KEY is using a development default"**
- Solution: Set `SECRET_KEY` environment variable to 32+ character random string

**Issue: "DATABASE_URL environment variable is required in production"**
- Solution: Add `DATABASE_URL` to environment variables in Render dashboard

**Issue: "SQLite is not supported in production"**
- Solution: Ensure `DATABASE_URL` points to PostgreSQL, not SQLite

**Issue: App fails to start with 500 errors**
- Check logs: Look for database connection errors
- Verify DATABASE_URL is correct: Format should be `postgresql://...`
- Run migrations: Migrations run automatically during build (`flask db upgrade`)

**Issue: Slow response times**
- Increase workers in Procfile: Change `--workers 2` to higher number
- Upgrade instance type in Render dashboard
- Check database instance size

### Database Migrations

Migrations run automatically during deployment via Procfile:
```
release: flask db upgrade
```

To manually run migrations after deployment:
```bash
# In Render dashboard, go to Web Service → Shell
flask db upgrade
```

## Performance Optimization

### 1. Enable CDN

Render provides automatic CDN for static assets. No configuration needed.

### 2. Configure Connection Pooling

Already optimized in config with:
- `DB_POOL_SIZE=5`
- `DB_MAX_OVERFLOW=10`
- `DB_POOL_RECYCLE=1800`

### 3. Monitor Resource Usage

In Render dashboard:
- Watch CPU usage (target: <50% normal operation)
- Monitor memory usage (target: <80%)
- Check database connections

Upgrade if:
- CPU consistently >70%
- Memory consistently >85%
- Database connections maxed out

## Scaling

### As You Grow

1. **Database**: Upgrade to Standard tier with more compute
2. **Web Service**: Increase instance size and worker count
3. **Caching**: Add Redis for rate limiting and session storage
4. **CDN**: Distribute static assets globally

### Multi-Instance Deployment

For horizontal scaling with multiple web service instances:

1. Add Redis for shared rate limiting:
   - Create Redis database on Render
   - Set `RATELIMIT_STORAGE_URI=` to Redis URL

2. Use managed PostgreSQL connection pooling (PgBouncer)

## Backup & Recovery

### Enable Automated Backups (Render PostgreSQL)

PostgreSQL databases on Render automatically backup daily. To restore:

1. In Render database dashboard, click **Backups**
2. Select backup point
3. Click **Restore**

### Manual Database Backup

```bash
# From local development environment
pg_dump $DATABASE_URL > stylebridge_backup.sql

# Restore from backup
psql $DATABASE_URL < stylebridge_backup.sql
```

## SSL/TLS Certificates

Render automatically provisions free SSL certificates via Let's Encrypt. No configuration needed.

Certificates auto-renew 30 days before expiration.

## Environment-Specific Configuration

### Development (Local)

```bash
FLASK_ENV=development
DEBUG=true
SESSION_COOKIE_SECURE=false
FORCE_HTTPS=false
DATABASE_URL=sqlite:///instance/app.db
```

### Production (Render)

```bash
FLASK_ENV=production
DEBUG=false
SESSION_COOKIE_SECURE=true
FORCE_HTTPS=true
DATABASE_URL=postgresql://...
TRUST_PROXY_HEADERS=true
```

## Support & Troubleshooting

### Getting Help

1. **Check Render docs**: https://render.com/docs
2. **View app logs**: Render dashboard → Logs
3. **Test locally first**: Deploy to production only after testing locally

### Testing Deployment Locally

Before pushing to production:

```bash
# Create .env.local with production settings
FLASK_ENV=production
DEBUG=false
SECRET_KEY=test-secret-key-at-least-32-chars-long
DATABASE_URL=sqlite:///instance/test.db
FORCE_HTTPS=false  # OK locally for testing

# Run locally
python run.py
```

## Rollback Procedure

If deployment fails:

1. Go to Render dashboard → Web Service
2. Click **Deployments** tab
3. Select previous successful deployment
4. Click **Redeploy**

Takes 1-2 minutes, no data loss.

## Next Steps

After successful deployment:

1. **Monitor in production**: Set up uptime monitoring (Render provides free status page)
2. **Test user flows**: Go through complete onboarding, wardrobe, recommendations
3. **Collect feedback**: Monitor error logs, user behavior
4. **Iterate**: Deploy updates regularly

## Production Deployment Checklist

Before going live:

- [ ] All environment variables set in Render
- [ ] PostgreSQL database created and connected
- [ ] Database migrations run successfully
- [ ] HTTPS working (automatic on Render)
- [ ] Admin account created and verified
- [ ] Tested complete user registration flow
- [ ] Tested login and session persistence
- [ ] Tested wardrobe upload and storage
- [ ] Tested recommendations generation
- [ ] Security headers verified
- [ ] Rate limiting working
- [ ] Logs available and readable
- [ ] Backup/restore tested

---

**Ready to deploy?** Follow the steps above, and your StyleBridge instance will be live in minutes.

For detailed backend architecture documentation, see `docs/render-deploy.md` and `docs/render-24-7-deploy.md`.
