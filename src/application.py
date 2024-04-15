import os
import json

from fastapi import APIRouter, FastAPI, HTTPException, Response

import logging

from src.timeseries import get_timeseries_at_pixel, layer_types
from src.HDF import open_dataset, datasets_path, read_layer_as_png_buffer, get_wkt_from_dataset

from . import log_router

router = APIRouter(route_class=log_router.LoggingRoute)
app = FastAPI()

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


@app.get("/items/{file_name}/layers/{layer}", description=f'Takes a valid file name and reads a layer from it, converted to a png')
def read_item(file_name: str, layer: str):
    if layer not in layer_types:
        raise HTTPException(
            400, f"{layer} is not a valid layer type. Valid Layer Types: {layer_types}"
        )    
    
    png_buffer = read_layer_as_png_buffer(file_name=file_name, layer=layer)
    return Response(content=png_buffer.getvalue(), headers={"Content-Disposition": 'inline; filename="test.png"', **DEFAULT_HEADERS}, media_type="image/png")

@app.get("/items/{file_name}/wkt", description=f'Returns a json response with the wkt and epsg of the file')
def get_wkt(file_name: str):
    data = open_dataset(file_name=file_name)
    identification = open_dataset(file_name=file_name, group='identification')
    output = get_wkt_from_dataset(data, identification)
    return Response(content=json.dumps(output), media_type='application/json', headers=DEFAULT_HEADERS)


@app.get("/timeseries", description=f'Returns a json response with ')
def get_time_series(x: float = 0, y: float = 0):
    # epsg: 32610

    logging.debug(f'Sampling timeseries at lon {x}, lat {y}')
    time_series, averages = get_timeseries_at_pixel(x=x,y=y, file_stack=[file for file in os.listdir(datasets_path) if file.endswith(".nc")])
    
    return Response(content=json.dumps({'time_series': time_series, 'coordinates': [x, y], 'averages': averages}), media_type='application/json', headers=DEFAULT_HEADERS)
