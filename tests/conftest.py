"""Isolate persistence and external delivery before importing application settings."""
import os

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['SMTP_USER'] = ''
os.environ['SMTP_PASSWORD'] = ''
os.environ['SECRET_KEY'] = 'fixture-only-jwt-key-with-at-least-32-characters'
os.environ['STRIPE_SECRET_KEY'] = 'sk_test'
os.environ['STRIPE_WEBHOOK_SECRET'] = 'whsec_test'
os.environ['PAYMENT_PROVIDER'] = 'stripe'
