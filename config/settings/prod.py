"""
Production settings — all sensitive values come from environment variables.
"""
from config.settings.base import *  # noqa: F401,F403
from config.settings.base import CSRF_TRUSTED_ORIGINS, SECRET_KEY, env_bool, env_list

DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith("insecure") or SECRET_KEY.startswith("dev-only"):
    raise RuntimeError("Set a strong SECRET_KEY for production.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS must be set in production.")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = env_bool("ENABLE_HSTS", True) and 31536000 or 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
