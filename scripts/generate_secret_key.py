#!/usr/bin/env python
"""Small helper to generate a secure Django SECRET_KEY for setting in env.
Usage: python scripts/generate_secret_key.py
"""
import secrets

def generate_key(length=50):
    # Django secret key needs printable ascii; token_urlsafe returns base64-like string
    return secrets.token_urlsafe(length)[:length]

if __name__ == '__main__':
    print(generate_key())
