from fastapi import HTTPException


class MissingFrameException(HTTPException):
    """No stack frame data found for given wkt"""
