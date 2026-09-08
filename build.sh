#!/usr/bin/env bash
# build.sh — Render Build Script
#
# Render runs this script during the Build phase, before Gunicorn starts.
# All three steps must succeed; if any step fails the build fails and
# the new version is NOT deployed (set -e enforces this).
#
# Render Start Command: gunicorn todo_project.wsgi:application
# (also defined in Procfile)

set -e  # Exit immediately if any command fails

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Running database migrations"
python manage.py migrate --noinput

echo "==> Running production initialisation (superuser + seed tags)"
python manage.py initialize_production

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Build complete"
