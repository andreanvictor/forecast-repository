"""
WSGI config for forecasts project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/
"""

from django.core.wsgi import get_wsgi_application


# NB: expects DJANGO_SETTINGS_MODULE to be set

application = get_wsgi_application()
