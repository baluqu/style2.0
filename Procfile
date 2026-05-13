release: flask db upgrade
web: gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 30 --access-logfile - --error-logfile - wsgi:app
