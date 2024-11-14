import time
import logging
from flask import request, g

api_logger = logging.getLogger("api_logger")
api_logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] %(aws_request_id)s %(levelname)s: %(message)s"))
api_logger.addHandler(handler)

class LoggingMiddleware:
    """
    Middleware for logging request and response information.
    """

    def __init__(self, app):
        self.app = app
        self.old_factory = logging.getLogRecordFactory()
        self.aws_request_id = ""

    def record_factory(self, *args, **kwargs):
        """
        Add extra info to the logger for each request.
        """
        record = self.old_factory(*args, **kwargs)
        record.aws_request_id = self.aws_request_id
        return record

    def __call__(self, environ, start_response):
        """
        The WSGI middleware to log request and response info.
        """
        with self.app.app_context():
            g.start_time = time.time()

            aws_context = environ.get("HTTP_X_AMZN_TRACE_ID")
            if aws_context:
                self.aws_request_id = aws_context

            logging.setLogRecordFactory(self.record_factory)

            def custom_start_response(status, headers, *args):
                """
                Add headers and calculate response time.
                """
                path = request.path
                req_args = request.args.to_dict()
                duration = time.time() - g.start_time
                headers.append(("X-Response-Time", str(duration)))
    
                api_logger.info(
                    f"Query to {path} with args {req_args} finished running with duration {duration}."
                )

                return start_response(status, headers, *args)

            response = self.app(environ, custom_start_response)

            api_logger.info(
                "Query was successful!",
                extra={
                    "media_type": response.content_type if hasattr(response, "content_type") else "unknown",
                },
            )

            return response
