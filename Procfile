web: gunicorn phoneinone_server.wsgi:application --bind 0.0.0.0:$PORT
worker: celery -A phoneinone_server worker --loglevel=info
beat: celery -A phoneinone_server beat -l info