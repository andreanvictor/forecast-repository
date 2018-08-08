from .base import *


DEBUG = True

SECRET_KEY = '&6kqgmf2fi3==##07k$!ns_#sd1%v4e4%$lbgft9(c7ar9itbh'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'forecast_repo',
        'USER': 'cornell',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}

#
# ---- Django-RQ config ----
#

RQ_QUEUES = {
    'default': {
        'URL': 'redis://localhost:6379/0',
        'DEFAULT_TIMEOUT': 360,
    },
}
