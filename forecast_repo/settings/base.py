"""
Django settings for forecast_repo project.

Generated by 'django-admin startproject' using Django 1.11.4.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

import logging
import os

from django.conf import settings


#
# directories
#

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = ...  # set by 'children' modules that: from .base import *

INSTALLED_APPS = [

    # the REST API
    'rest_framework',

    # this application
    'forecast_app.apps.ForecastAppConfig',

    # django.contrib.admin (and friends) is listed after the make_cdc_flu_contests_project_app application b/c o/w it
    # overrides the registration/logged_out.html template used by this application
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # add-ons
    'django.contrib.humanize',
    'debug_toolbar',
    'django_rq',
    'anymail',
    'compressor'
]

REST_FRAMEWORK = {
    # 'DEFAULT_PERMISSION_CLASSES': [
    #     'rest_framework.permissions.AllowAny',  # default
    # ],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_jwt.authentication.JSONWebTokenAuthentication',  # djangorestframework-jwt
        # 'rest_framework.authentication.SessionAuthentication',  # default
        # 'rest_framework.authentication.BasicAuthentication',  # ""
    ),
    'PAGE_SIZE': 10
}

DATA_UPLOAD_MAX_NUMBER_FIELDS = 2500  # editing Projects involves possibly many <input> fields dep. on # of TimeZeros

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'forecast_app.middleware.AuthenticationMiddlewareJWT',
]

ROOT_URLCONF = 'forecast_repo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # 'DIRS': [],
        # https://stackoverflow.com/questions/25991081/cant-modify-django-rest-framework-base-html-file :
        'DIRS': [os.path.join(BASE_DIR, 'templates')],

        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'forecast_repo.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),  # https://github.com/torchbox/django-libsass -> {% compress css %}
)

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_L10N = True

USE_TZ = True

if not settings.DEBUG:  # NB: requires "children" settings to set DEBUG before importing
    SECURE_SSL_REDIRECT = True

#
# set up logging - https://stackoverflow.com/questions/5137042/how-can-i-get-django-to-print-the-debug-information-to-the-console
# note: According to docs, I should not have to specify this - default should be to log everything INFO and higher to
# console - https://docs.djangoproject.com/en/1.11/topics/logging/#default-logging-configuration
#

# disable noise from boto3, per https://stackoverflow.com/questions/1661275/disable-boto-logging-without-modifying-the-boto-files
for name in ['boto', 'urllib3', 's3transfer', 'boto3', 'botocore', 'nose']:
    logging.getLogger(name).setLevel(logging.CRITICAL)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'NOTSET',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'NOTSET',
        },
    }
}

#
# https://docs.djangoproject.com/en/1.11/ref/settings/#std:setting-LOGIN_REDIRECT_URL
#

# Redirect to home URL after login (Default redirects to /accounts/profile/)
LOGIN_REDIRECT_URL = '/'

#
# https://django-debug-toolbar.readthedocs.io/en/stable/installation.html#internal-ips
#
INTERNAL_IPS = ['127.0.0.1']

#
# set tags to match Bootstrap 3, https://coderwall.com/p/wekglq/bootstrap-and-django-messages-play-well-together
#

from django.contrib.messages import constants as message_constants


MESSAGE_TAGS = {
    # message_constants.DEBUG: 'debug',
    # message_constants.INFO: 'info',
    # message_constants.SUCCESS: 'success',
    # message_constants.WARNING: 'warning',
    message_constants.ERROR: 'danger',  # the only one that needs correcting, i.e., the only one different from default
}

#
# ---- Django-RQ queue name variables. used by "inheriting" settings files ----
#

HIGH_QUEUE_NAME = 'high'
DEFAULT_QUEUE_NAME = 'default'
LOW_QUEUE_NAME = 'low'

# here's the mapping of all RQ-related functionality to specific queues. NB: when adding new functionality, add new
# variables here.

# high
UPLOAD_FILE_QUEUE_NAME = HIGH_QUEUE_NAME
DELETE_FORECAST_QUEUE_NAME = HIGH_QUEUE_NAME
QUERY_FORECAST_QUEUE_NAME = HIGH_QUEUE_NAME

# default
ROW_COUNT_UPDATE_QUEUE_NAME = DEFAULT_QUEUE_NAME
UPDATE_PROJECT_SCORE_CSV_FILE_CACHE_QUEUE_NAME = DEFAULT_QUEUE_NAME
CACHE_FORECAST_METADATA_QUEUE_NAME = DEFAULT_QUEUE_NAME

# low
UPDATE_MODEL_SCORES_QUEUE_NAME = LOW_QUEUE_NAME

#
# S3 support - used by cloud_file.py
#

S3_BUCKET_PREFIX = os.environ.get('S3_BUCKET_PREFIX')

if not S3_BUCKET_PREFIX:
    raise RuntimeError('base.py: S3_BUCKET_PREFIX not configured!')

#
# support for sending emails per https://www.sendinblue.com/ by way of https://github.com/anymail/django-anymail
#

ANYMAIL = {
    'SENDINBLUE_API_KEY': os.environ.get('SENDINBLUE_API_KEY'),
}

EMAIL_BACKEND = 'anymail.backends.sendinblue.EmailBackend'

DEFAULT_FROM_EMAIL = 'admin@zoltardata.com'

#
# ---- static files config ----
#

# the absolute path to the directory where collectstatic will collect static files for deployment:
STATIC_ROOT = os.path.join(PROJECT_ROOT, 'staticfiles')

# URL to use when referring to static files located in STATIC_ROOT:
STATIC_URL = '/static/'

# additional locations the staticfiles app will traverse if the FileSystemFinder finder is enabled:
STATICFILES_DIRS = [
    os.path.join(PROJECT_ROOT, 'static'),
]

# the file storage engine to use when collecting static files with the collectstatic management command:
# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# the list of finder backends that know how to find static files in various locations:
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder'  # Django-Compressor
]

#
# Django Compressor
#

# https://medium.com/technolingo/fastest-static-files-served-django-compressor-whitenoise-aws-cloudfront-ef777849090c
# https://www.accordbox.com/blog/how-use-scss-sass-your-django-project-python-way/

COMPRESS_STORAGE = 'compressor.storage.GzipCompressorFileStorage'
# COMPRESS_ENABLED = True  # must enable this to use with Whitenoise. default: the opposite of DEBUG
COMPRESS_OFFLINE = True  # "". default: False

LIBSASS_OUTPUT_STYLE = 'compressed'  # default: 'nested'

#
# set configurable zoltar variables
#

# number of rows beyond which `query_forecasts_for_project()` raises a "too many rows" error
MAX_NUM_QUERY_ROWS = 200_000

if 'MAX_NUM_QUERY_ROWS' in os.environ:
    max_num_query_rows_value = os.environ.get('MAX_NUM_QUERY_ROWS')
    try:
        MAX_NUM_QUERY_ROWS = float(max_num_query_rows_value)
    except ValueError:
        raise RuntimeError(f"base.py: MAX_NUM_QUERY_ROWS config var could not be coerced to float: "
                           f"{max_num_query_rows_value!r}")

# used by file uploading methods to limit them from being too large:
MAX_UPLOAD_FILE_SIZE = 10E+06

if 'MAX_UPLOAD_FILE_SIZE' in os.environ:
    max_upload_file_size_value = os.environ.get('MAX_UPLOAD_FILE_SIZE')
    try:
        MAX_UPLOAD_FILE_SIZE = float(max_upload_file_size_value)
    except ValueError:
        raise RuntimeError(
            f"base.py: MAX_UPLOAD_FILE_SIZE config var could not be coerced to float: "
            f"{max_upload_file_size_value!r}")
