# Hosting Options (No Cloudflare Tunnel)

Cloudflare quick tunnels are useful for short tests, but not a reliable public product URL. Use a hosted service instead.

## Recommended order

1. **Render** (best fit for this Flask app + 3D static assets)
2. **PythonAnywhere** (very beginner-friendly Flask hosting)
3. **Railway** (good fallback if Render free limits block you)

## Render quick path

1. Push repo to GitHub.
2. Deploy using [`render.yaml`](../render.yaml) via Render Blueprint.
3. Confirm:
   - `/health` returns `ok`
   - `/demo` works from incognito
   - GLB upload + preview works

## PythonAnywhere quick path

1. Create account.
2. Upload project or clone repo.
3. Create virtualenv and install `requirements.txt`.
4. Configure WSGI to use `wsgi:app`.
5. Set env vars in PythonAnywhere web app settings.

## Railway quick path

1. Connect GitHub repo.
2. Set start command to `gunicorn wsgi:app --bind 0.0.0.0:$PORT`.
3. Set production env vars (`FLASK_ENV`, `SECRET_KEY`, `ADMIN_KEY`, secure cookie flags).
4. Verify `/health`.

