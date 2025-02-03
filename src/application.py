from fastapi import APIRouter, FastAPI, HTTPException, Response
from pathlib import Path
from time import perf_counter
import logging

from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from src.exceptions import MissingFrameException
from src.models import (
    TimeSeriesModel,
    GetFramesModel,
)
from src.timeseries import get_timeseries_over_aoi
from src import api_logger
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

class ReadLayer(BaseModel):
    file_name: str
    layer: str

@app.post(
    '/timeseries',
    description='Returns a json response with values read at "unwrapped_phase", "interferometric_correlation", and "temporal_coherence" layers in provided files at given point',
)
def get_timeseries(series: TimeSeriesModel):
    start = perf_counter()
    try:
        geometry = shapely_wkt.loads(series.wkt)
    except BaseException as exc:
        raise HTTPException(
            400, detail=f'Failed to load provided wkt string. Original Error: {exc}'
        )

    api_logger.debug(f'wkt loaded: {geometry.wkt}')

    zarr_stores = _get_available_file_stores_for_wkt(series)

    file_store = zarr_stores[0]
    api_logger.info(f'using file store: {file_store}')

    try:
        output_str = get_timeseries_over_aoi(
            geometry=geometry,
            file_store=file_store,
        )
    except BaseException as exc:
        raise HTTPException(
            500, detail=f'Failed to calculate timeseries. Original Exception: {exc}'
        )

    api_logger.info(f'Query time: {perf_counter() - start} seconds')
    return Response(content=output_str, media_type='application/json', headers=DEFAULT_HEADERS)


@app.post(
    '/get_frame_id',
    description='Returns the frame ids for a given aoi',
)
def get_frame_ids(wkt_event: GetFramesModel):
    return JSONResponse(
        {'frame_ids': sorted(_get_frames_for_wkt(wkt_event.wkt, wkt_event.flightDirection)), 'wkt': wkt_event.wkt},
        headers=DEFAULT_HEADERS,
    )


def _get_available_file_stores_for_wkt(params: TimeSeriesModel):
    # example:
    # s3://asf-cumulus-test-opera-products/OPERA_L3_DISP-S1_STACK_V1/OPERA_L3_DISP-S1_IW_F44328_VV_V1/OPERA_L3_DISP-S1_IW_F44328_VV_short_wavelength_displacement.zarr.json.gz
    
    polarization = params.polarization.value

    zarr_stores = [
        # f's3://{params.bucket}/OPERA_L3_DISP-S1_IW_F{frame_id}_{polarization}.json.zarr.gz'
        f's3://{params.bucket}/OPERA_L3_DISP-S1_STACK_V1/OPERA_L3_DISP-S1_IW_F{frame_id}_{polarization}_V1/OPERA_L3_DISP-S1_IW_F{frame_id}_{polarization}_short_wavelength_displacement.zarr.json.gz'
        for frame_id in _get_frames_for_wkt(params.wkt, params.flightDirection)
    ]

    s3 = s3fs.S3FileSystem(anon=False)
    
    available_zarr_stores = []
    for store in zarr_stores:
        try:
            if s3.exists(store):
                available_zarr_stores.append(store)
        except Exception as exc:
            logging.debug(f'Failed to open store "{store}". Original exception: {exc}')

    if len(available_zarr_stores) == 0:
        raise MissingFrameException(
            400, f'No data found for the given area of interest {params.wkt}'
        )

    return available_zarr_stores


def _get_frames_for_wkt(wkt: str, flight_direction: str) -> list[str]:
    frame_path = Path(__file__).parent.parent / 'data' / 'frames.geojson'
    geometry = shapely_wkt.loads(wkt)
    gdf = gpd.read_file(frame_path, engine='pyogrio')
    result = gdf[gdf.orbit_direction==flight_direction][gdf.intersects(geometry)]
    frame_ids = set(result['frame_id'])

    if len(frame_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail=f'No OPERA-S1 burst frame ids were found over the given aoi: {wkt}',
        )

    frame_strings = []
    
    for frame in frame_ids:
        frame_str = str(frame)

        # append leading zeros
        if len(frame_str) < 5:
            frame_str = ('0'*(5-len(frame_str))) + frame_str

        frame_strings.append(str(frame))
    
    return sorted(frame_strings)
    # return JSONResponse({'frame_ids': sorted(list(frame_ids)), 'wkt': wkt}, headers=DEFAULT_HEADERS)
