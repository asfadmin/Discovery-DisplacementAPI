import serverless_wsgi

from src import create_app

app = create_app()

serverless_wsgi.TEXT_MIME_TYPES.append('application/problem+json')

def handler(event, context):
    return serverless_wsgi.handle_request(app.wsgiapp, event, context)
