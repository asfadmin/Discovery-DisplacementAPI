import os
import json
from typing import List

from fastapi import APIRouter, FastAPI, HTTPException, Response

import logging

from mangum import Mangum
from pydantic import BaseModel

from src.HDF.data_reader import open_datasets
from src.timeseries import get_timeseries_at_pixel, layer_types
from src.HDF import open_dataset, datasets_path, read_layer_as_png_buffer, get_wkt_from_dataset

from . import log_router
import fsspec
router = APIRouter(route_class=log_router.LoggingRoute)
app = FastAPI()

lambda_handler = Mangum(
    app
    )
DEFAULT_HEADERS = {
    "Access-Control-Allow-Origin": "*",
}

import numpy as np

@app.get("/")
def read_root():
    return {"Status": "A-Okay"}

# TODO: Remove when working with actual data
@app.get("/items", description='(For Development Only): Returns a json response with a single key, "files", a list of files available to read from')
def get_items_list():
    nc_files = [file for file in os.listdir(datasets_path) if file.endswith(".nc")]
    return Response(content=json.dumps({"files": nc_files}), media_type='application/json', headers=DEFAULT_HEADERS
    )

# TODO: Remove this endpoint when browses are available
@app.get("/items/layers", description=f'(For Development Only): Takes a valid file name and reads a layer from it, converted to a png with nan values as alpha channel')
def read_item(file_name: str, layer: str):
    if layer not in layer_types:
        raise HTTPException(
            400, f"{layer} is not a valid layer type. Valid Layer Types: {layer_types}"
        )    
    
    png_buffer = read_layer_as_png_buffer(file_name=file_name, layer=layer)
    return Response(content=png_buffer.getvalue(), headers={"Content-Disposition": 'inline; filename="test.png"', **DEFAULT_HEADERS}, media_type="image/png")

@app.get("/items/wkt", description=f'Returns a json response with the wkt and epsg of the file')
def get_wkt(file_name: str):
    data = open_dataset(file_name=file_name)
    identification = open_dataset(file_name=file_name, group='identification')
    output = get_wkt_from_dataset(data, identification)
    return Response(content=json.dumps(output), media_type='application/json', headers=DEFAULT_HEADERS)

class   TimeSeriesModel(BaseModel):
    files: List[str]
    x: float = 0.0
    y: float = 0.0

# TODO: Test these out

@app.post("/timeseries", description=f'Returns a json response with ')
def get_time_series(series: TimeSeriesModel):
    # epsg: 32610
    x = series.x
    y = series.y
    files = series.files
    from time import time
    perf = time()
    # d = open_datasets(files, 'unwrapped_phase') # group not found for some reason
    perf = time() - perf
    logging.debug(f'Sampling timeseries at lon {x}, lat {y}')
    values, averages = get_timeseries_at_pixel(x=x,y=y, file_stack=[file for file in files])
    output = json.loads(values)
    output['averages'] = averages
    return Response(content=json.dumps(output), media_type='application/json', headers=DEFAULT_HEADERS)
