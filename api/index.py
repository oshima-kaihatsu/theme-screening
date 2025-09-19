from flask import Flask
import sys
import os

# Add the parent directory to Python path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from theme_web_app import app

# Vercel expects the Flask app to be available as 'app'
# This is the entry point for Vercel serverless functions
def handler(request):
    return app(request.environ, lambda status, headers: None)