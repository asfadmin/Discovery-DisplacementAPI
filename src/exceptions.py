from fastapi import HTTPException


class MissingFrameException(HTTPException):
    """No stack frame data found for given wkt"""

class OutdatedStackException(HTTPException):
    """Found stack has no up-to-date data (product version < 1.0)"""