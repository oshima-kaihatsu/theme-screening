import sys
import os

# Add the parent directory to Python path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app from theme_web_app
from theme_web_app import app

# Export the app for Vercel
# Vercel will automatically handle the WSGI interface