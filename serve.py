import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings.development")

print("Starting serve.py")
from waitress import serve
from project.wsgi import application
print("Imported application")

if __name__ == "__main__":
    port = int(os.environ.get("HTTP_PLATFORM_PORT", 8000))
    print(f"Serving on port {port}")
    serve(application, host="0.0.0.0", port=port)