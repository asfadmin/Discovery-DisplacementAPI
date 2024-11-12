import json

from fastapi import APIRouter, FastAPI, HTTPException, Response

import logging

from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# from mangum import Mangum
from pydantic import BaseModel
from src.models import (
    FsspecParams,
    TimeSeriesModel,
    WKTModel,
)
from src.timeseries import layer_types, get_timeseries_over_aoi
from src.HDF import read_layer_as_png_buffer
import s3fs
import geopandas as gpd

from . import log_router
from shapely import wkt as shapely_wkt

router = APIRouter(route_class=log_router.LoggingRoute)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)
DEFAULT_HEADERS = {
    'Access-Control-Allow-Origin': '*',
}


@app.get('/')
def read_root():
    return {'Status': 'A-Okay'}


# TODO: Remove when working with actual data in CMR
@app.get(
    '/items',
    description='(For Development Only): Returns a json response with a single key, "files", a list of files available to read from',
)
def get_items_list():
    s3 = s3fs.S3FileSystem()
    files = s3.glob('s3://kfbx-opera-disp-test-bucket/*.nc')
    return Response(
        content=json.dumps({'files': files}),
        media_type='application/json',
        headers=DEFAULT_HEADERS,
    )


class ReadLayer(BaseModel):
    file_name: str
    layer: str


# TODO: Remove when working with actual data in CMR
@app.post(
    '/items/layers',
    description='(For Development Only): Takes a valid file name and reads a layer from it, converted to a png with nan values as alpha channel',
)
def read_item(data: ReadLayer):
    if data.layer not in layer_types:
        raise HTTPException(
            400,
            f'{data.layer} is not a valid layer type. Valid Layer Types: {layer_types}',
        )

    png_buffer = read_layer_as_png_buffer(file_name=data.file_name, layer=data.layer)
    return Response(
        content=png_buffer.getvalue(),
        headers={
            'Content-Disposition': 'inline; filename="test.png"',
            **DEFAULT_HEADERS,
        },
        media_type='image/png',
    )


# TODO: Remove when working with actual data in CMR
@app.get(
    '/items/wkt',
    description='(For Development Only): Returns a static json response with the wkt of the test products (currently over california)',
)
def get_wkt():
    return JSONResponse(
        {
            'epsg': 32610,
            'wkt': 'POLYGON ((-149.451139279365 62.1287442968912, -149.489207371942 62.045616952959, -149.476221395717 62.0129791068178, -149.519088628246 61.955889388159, -149.536405309494 61.854259222719, -149.586547633797 61.725062981579, -149.594933718237 61.6491856726608, -149.81365221469 60.9678772131571, -149.835750622071 60.9420795477735, -149.859662107215 60.8380786660427, -149.904017634358 60.7487221866998, -149.925244567858 60.643143005989, -148.495889771202 60.5277410743715, -148.470041402483 60.584602367533, -146.906606463731 60.4396563701975, -146.873685244838 60.4951172124558, -145.386267125578 60.3396641673686, -145.290423628369 60.5402632158137, -145.280500106703 60.5829732084687, -145.301225650796 60.5845853001108, -145.236822870895 60.6909796637016, -145.247262492305 60.7010850131082, -145.224251585634 60.7495463006203, -145.232581050756 60.7682458705588, -145.187153890321 60.8021251581012, -145.208019152527 60.8234194914492, -145.058111527729 61.0387595374364, -145.099374030659 61.0732930019398, -145.024138665138 61.1204393557309, -145.047326954518 61.1417906129957, -145.030470686787 61.1886939957555, -144.963180408383 61.2453544268513, -144.984671478238 61.2677677145688, -144.976235627719 61.337959599446, -144.89834894171 61.4289187444297, -144.910469614585 61.4579328980322, -144.890927390867 61.4721803217938, -144.897062103683 61.4897872096134, -144.874529671332 61.5309281203528, -144.843140879426 61.5522585942678, -144.843705014899 61.5929497163114, -144.762933706766 61.6622405486587, -144.700945264316 61.8174811273622, -146.289453228815 61.9803053628305, -146.329597119308 61.9247592198443, -147.983354118586 62.073430473257, -148.010743582664 62.0164065972356, -149.451139279365 62.1287442968912))',
        },
        headers=DEFAULT_HEADERS,
    )


@app.post(
    '/timeseries',
    description='Returns a json response with values read at "unwrapped_phase", "interferometric_correlation", and "temporal_coherence" layers in provided files at given point',
)
def get_timeseries(series: TimeSeriesModel):
    # epsg: 32610
    file_store = series.file_store
    target_files = series.target_files

    try:
        geometry = shapely_wkt.loads(series.wkt)
    except BaseException as exc:
        raise HTTPException(
            400, detail=f'Failed to load provided wkt string. Original Error: {exc}'
        )

    logging.debug(f'wkt loaded: {geometry.wkt}')

    # logging.debug(f'Sampling timeseries at lat {lat}, lon {lon}')
    if series.fsspec_params is None:
        series.fsspec_params = FsspecParams()

    try:
        output_str = get_timeseries_over_aoi(
            geometry=geometry,
            file_store=file_store,
            target_files=target_files,
            fsspec_params=series.fsspec_params,
        )
    except BaseException as exc:
        raise HTTPException(
            500, detail=f'Failed to calculate timeseries. Original Exception: {exc}'
        )

    return Response(content=output_str, media_type='application/json', headers=DEFAULT_HEADERS)


@app.post(
    '/get_frame_id',
    description='Returns a json zarr store bytes',
)
def get_frame_ids(wkt_event: WKTModel):
    wkt = wkt_event.wkt
    geometry = shapely_wkt.loads(wkt)
    gdf = gpd.read_file('frames.geojson', engine='pyogrio')
    result = gdf[gdf.intersects(geometry)]
    frame_ids = set(result['frame_id'])

    if len(frame_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail=f'No OPERA-S1 burst frame ids were found over the given aoi: {wkt}',
        )

    return JSONResponse({'frame_ids': sorted(list(frame_ids)), 'wkt': wkt}, headers=DEFAULT_HEADERS)
