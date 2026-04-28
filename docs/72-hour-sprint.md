# 72-Hour Execution Plan (No Cloudflare Tunnel)

## Hours 0-12: Hosting + Auth Smoke Test

1. Push code to GitHub (public or private).
2. Deploy to Render using [`render.yaml`](../render.yaml).
3. Set production env vars in Render:
   - `FLASK_ENV=production`
   - `SECRET_KEY` (generated)
   - `ADMIN_KEY` (generated)
   - `FORCE_HTTPS=true`
   - `TRUST_PROXY_HEADERS=true`
4. Confirm live checks:
   - `/health` returns `ok`
   - `/demo` loads from incognito
   - `/auth/register` creates account and redirects to `/demo`
   - `/auth/login` redirects to `/demo`

## Hours 12-36: Demo Reliability

1. Validate all sample GLBs load:
   - `/static/models/toji-reference.glb`
   - `/static/models/formal-olive-look.glb`
   - `/static/models/satin-slip-dress.glb`
2. Validate guest model upload in `/demo`.
3. Validate motion, lighting, and palette controls.
4. Validate share + export buttons:
   - Share copies public URL with `?model=...`
   - Export downloads PNG screenshot

## Hours 36-72: Growth Basics

1. Keep home page simple:
   - One primary CTA (`Try Demo Now`)
   - Honest social proof placeholder
2. Keep feedback/social links visible on every page (footer).
3. Add manual analytics review:
   - Check Render request logs daily
   - Track visits to `/`, `/demo`, `/feedback`
