import os


if os.environ.get("DJANGO_MODULE_STR") == 'develop':
    from .develop import *
else:
    from .production import *

