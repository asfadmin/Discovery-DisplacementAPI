# pylint: disable=wrong-import-position

# (api_logger needs to be created before
# the "from . import"'s to avoid a circular import)
# import logging

# from fastapi import APIRouter, FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from src import logger
# api_logger = logger.get_logger(__name__, logging.DEBUG)
# from src import log_router

# router = APIRouter(route_class=log_router.LoggingRoute)

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=['*'],
#     allow_methods=['*'],
#     allow_headers=['*'],
# )

# from src import models  # noqa: E402, F401
# from src import application  # noqa: E402, F401
