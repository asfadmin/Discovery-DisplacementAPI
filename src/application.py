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
from shapely import convex_hull
from shapely.geometry.base import BaseGeometry

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
    if geometry.geom_type not in ['Polygon', 'Point']:
        raise HTTPException(
            400, detail=f'Failed to load provided wkt. Must be "POLYGON" or "POINT", got {geometry.geom_type.upper()}'
        )

    api_logger.debug(f'wkt loaded: {geometry.wkt}')

    file_store = _get_zarr_store_uri(
        bucket=series.bucket,
        wkt=series.wkt,
        frame_id=series.frameId,
        polarization=series.polarization.value,
        flight_direction=series.flightDirection
        )

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

@app.post(
    '/frame_intersection',
    description='Returns the frame ids for a given aoi, splitting any cross frames',
)
def frame_intersection(wkt_event: GetFramesModel):
    wkt = wkt_event.wkt
    flight_direction = wkt_event.flightDirection
    overlapping_frames = _get_frames_for_wkt(wkt, flight_direction)
    frame_path = Path(__file__).parent.parent / 'data' / 'frames.geojson'
    geometry = shapely_wkt.loads(wkt_event.wkt)
    gdf = gpd.read_file(frame_path, engine='pyogrio')
    frames: gpd.GeoDataFrame = gdf[gdf['frame_id'].isin([int(p) for p in overlapping_frames])] # type: ignore
    intersection = frames.intersection(geometry)
    return JSONResponse(
        {_pad_frame_str(frame_id): _simplify_multipolygons(geom).wkt for frame_id, geom in zip(gdf.iloc[intersection.index]['frame_id'], intersection)},
        headers=DEFAULT_HEADERS,
    )

def _simplify_multipolygons(geometry: BaseGeometry) -> BaseGeometry:
    """In case polygon intersects different sections of frame at once and get multi-polygon (swath corners for example), perform convex hull instead"""
    if geometry.geom_type == 'MultiPolygon':
        geometry = convex_hull(geometry)
    
    return geometry

def _pad_frame_str(frame: str):
    frame_str = str(frame)

    # append leading zeros
    if len(frame_str) < 5:
        frame_str = ('0'*(5-len(frame_str))) + frame_str

    return frame_str

def _get_file_store_for_wkt(bucket: str, frame_id: str, polarization: str):
    return f's3://{bucket}/OPERA_L3_DISP-S1_STACK_V1/OPERA_L3_DISP-S1_IW_F{frame_id}_{polarization}_V1/OPERA_L3_DISP-S1_IW_F{frame_id}_{polarization}_short_wavelength_displacement.zarr.json.gz'

def _get_zarr_store_uri(bucket: str, wkt: str, frame_id: str | None, polarization: str, flight_direction: str):
    if isinstance(frame_id, str): 
        zarr_store = _get_file_store_for_wkt(bucket=bucket, frame_id=frame_id, polarization=polarization)

        s3 = s3fs.S3FileSystem(anon=False)
        try:
            if s3.exists(zarr_store):
                return zarr_store
        except Exception as exc:
            logging.debug(f'Failed to open store "{zarr_store}". Original exception: {exc}')
        raise MissingFrameException(
            400, f'No data found for the given area of interest {wkt}'
        )
    else:
        return _get_available_file_stores_for_wkt(bucket=bucket, wkt=wkt, polarization=polarization, flight_direction=flight_direction)[0]

def _get_available_file_stores_for_wkt(bucket: str, wkt: str, polarization: str, flight_direction: str):
    # example:
    # s3://asf-cumulus-test-opera-products/OPERA_L3_DISP-S1_STACK_V1/OPERA_L3_DISP-S1_IW_F44328_VV_V1/OPERA_L3_DISP-S1_IW_F44328_VV_short_wavelength_displacement.zarr.json.gz
    
    zarr_stores = [
        _get_file_store_for_wkt(bucket=bucket, frame_id=frame_id, polarization=polarization)
        for frame_id in _get_frames_for_wkt(wkt, flight_direction)
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
            400, f'No data found for the given area of interest {wkt}'
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

        frame_strings.append(str(frame_str))
    
    return sorted(frame_strings)
    # return JSONResponse({'frame_ids': sorted(list(frame_ids)), 'wkt': wkt}, headers=DEFAULT_HEADERS)
