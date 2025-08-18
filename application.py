import os
import sys
from django.core.wsgi import get_wsgi_application

sys.path.append("/var/app/current")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "phoneinone_server.settings")
application = get_wsgi_application()
