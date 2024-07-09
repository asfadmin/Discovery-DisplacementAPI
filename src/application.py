import os
import json

from fastapi import APIRouter, FastAPI, HTTPException, Response

import logging

from mangum import Mangum
from src.models import DriverKeywords, FsspecParams, TimeSeriesModel
from src.timeseries import get_timeseries_at_pixel, layer_types
from src.HDF import open_dataset, datasets_path, read_layer_as_png_buffer, get_wkt_from_dataset

from . import log_router
router = APIRouter(route_class=log_router.LoggingRoute)
app = FastAPI()

lambda_handler = Mangum(
    app
    )
DEFAULT_HEADERS = {
    "Access-Control-Allow-Origin": "*",
}

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
@app.get("/items/layers", description='(For Development Only): Takes a valid file name and reads a layer from it, converted to a png with nan values as alpha channel')
def read_item(file_name: str, layer: str):
    if layer not in layer_types:
        raise HTTPException(
            400, f"{layer} is not a valid layer type. Valid Layer Types: {layer_types}"
        )    
    
    png_buffer = read_layer_as_png_buffer(file_name=file_name, layer=layer)
    return Response(content=png_buffer.getvalue(), headers={"Content-Disposition": 'inline; filename="test.png"', **DEFAULT_HEADERS}, media_type="image/png")

@app.get("/items/wkt", description='Returns a json response with the wkt and epsg of the file')
def get_wkt(file_name: str):
    data = open_dataset(file_name=file_name)
    identification = open_dataset(file_name=file_name, group='identification')
    output = get_wkt_from_dataset(data, identification)
    return Response(content=json.dumps(output), media_type='application/json', headers=DEFAULT_HEADERS)

# TODO: Test these out

@app.post("/timeseries", description='Returns a json response with values read at "unwrapped_phase", "interferometric_correlation", and "temporal_coherence" layers in provided files at given point')
def get_timeseries(series: TimeSeriesModel):
    # epsg: 32610
    x = series.x
    y = series.y
    files = series.files
    from time import time
    perf = time()
    # d = open_datasets(files, 'unwrapped_phase') # group not found for some reason
    perf = time() - perf
    logging.debug(f'Sampling timeseries at lon {x}, lat {y}')
    if series.fsspec_params is None:
        series.fsspec_params = FsspecParams()
    if series.driver_kwds is None:
        series.driver_kwds = DriverKeywords()
    values, averages = get_timeseries_at_pixel(x=x,y=y, file_stack=[file for file in files], fsspec_params=series.fsspec_params, driver_config=series.driver_kwds)
    output = json.loads(values)
    output['averages'] = averages
    return Response(content=json.dumps(output), media_type='application/json', headers=DEFAULT_HEADERS)
