"""Script to download static assets during Railway build"""
import urllib.request, os

os.makedirs('static/css', exist_ok=True)

try:
    url = 'https://cdn.tailwindcss.com/3.4.17'
    urllib.request.urlretrieve(url, 'static/css/tailwind.min.css')
    size = os.path.getsize('static/css/tailwind.min.css')
    print(f"✓ Tailwind downloaded: {size/1024:.0f} KB")
except Exception as e:
    print(f"Warning: Could not download Tailwind: {e}")
