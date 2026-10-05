"""
Development settings.
"""
from config.settings.base import *  # noqa: F401,F403
from config.settings.base import env_bool, env_list

DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,web,nginx")

# Dev cookies over HTTP
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
