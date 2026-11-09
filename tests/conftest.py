"""Isolate persistence and external delivery before importing application settings."""
import os

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['SMTP_USER'] = ''
os.environ['SMTP_PASSWORD'] = ''
os.environ.setdefault('SECRET_KEY', 'test-secret')
os.environ['STRIPE_SECRET_KEY'] = 'sk_test'
os.environ['STRIPE_WEBHOOK_SECRET'] = 'whsec_test'
