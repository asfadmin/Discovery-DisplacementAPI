import json
import logging
from flask import Blueprint, jsonify, request, Response
from pathlib import Path
from pydantic import BaseModel
from flask_cors import CORS
import s3fs
import geopandas as gpd
from shapely import wkt as shapely_wkt

from src.models import FsspecParams, TimeSeriesModel, WKTModel
from src.timeseries import layer_types, get_timeseries_over_aoi
from src.HDF import read_layer_as_png_buffer
from src.log_router import LoggingMiddleware

# Create a blueprint for routes
api_blueprint = Blueprint('api', __name__)

DEFAULT_HEADERS = {
    'Access-Control-Allow-Origin': '*',
}

@api_blueprint.route('/', methods=['GET'])
def read_root():
    return jsonify({'Status': 'A-Okay'})


@api_blueprint.route('/items', methods=['GET'])
def get_items_list():
    """(For Development Only): Returns a json response with a list of files available to read from"""
    s3 = s3fs.S3FileSystem()
    files = s3.glob('s3://kfbx-opera-disp-test-bucket/*.nc')
    return Response(
        response=json.dumps({'files': files}),
        mimetype='application/json',
        headers=DEFAULT_HEADERS,
    )


@api_blueprint.route('/items/layers', methods=['POST'])
def read_item():
    """(For Development Only): Reads a layer from a file and converts it to a PNG buffer"""
    data = request.get_json()
    file_name = data.get('file_name')
    layer = data.get('layer')

    if layer not in layer_types:
        return jsonify({'error': f'{layer} is not a valid layer type. Valid Layer Types: {layer_types}'}), 400

    png_buffer = read_layer_as_png_buffer(file_name=file_name, layer=layer)
    return Response(
        response=png_buffer.getvalue(),
        headers={
            'Content-Disposition': 'inline; filename="test.png"',
            **DEFAULT_HEADERS,
        },
        mimetype='image/png',
    )


@api_blueprint.route('/items/wkt', methods=['GET'])
def get_wkt():
    """(For Development Only): Returns a static WKT response"""
    return jsonify({
        'epsg': 32610,
        'wkt': 'POLYGON ((-149.451139279365 62.1287442968912, ...))'
    }), 200, DEFAULT_HEADERS


@api_blueprint.route('/timeseries', methods=['POST'])
def get_timeseries():
    """Returns a JSON response with values read from specified layers"""
    series_data = request.get_json()
    try:
        series = TimeSeriesModel(**series_data)
        geometry = shapely_wkt.loads(series.wkt)
    except Exception as exc:
        return jsonify({'error': f'Failed to load WKT or parse data. Error: {exc}'}), 400

    if series.fsspec_params is None:
        series.fsspec_params = FsspecParams()

    try:
        output_str = get_timeseries_over_aoi(
            geometry=geometry,
            file_store=series.file_store,
            target_files=series.target_files,
            fsspec_params=series.fsspec_params,
        )
    except Exception as exc:
        return jsonify({'error': f'Failed to calculate timeseries. Error: {exc}'}), 500

    return Response(response=output_str, mimetype='application/json', headers=DEFAULT_HEADERS)


@api_blueprint.route('/get_frame_id', methods=['POST'])
def get_frame_ids():
    """Returns a JSON response with frame IDs"""
    data = request.get_json()
    wkt = data.get('wkt')
    geometry = shapely_wkt.loads(wkt)

    frame_path = Path(__file__).parent.parent / 'data' / 'frames.geojson'
    gdf = gpd.read_file(frame_path, engine='pyogrio')
    result = gdf[gdf.intersects(geometry)]
    frame_ids = set(result['frame_id'])

    if not frame_ids:
        return jsonify({'error': f'No OPERA-S1 burst frame IDs were found for the given AOI: {wkt}'}), 400

    return jsonify({'frame_ids': sorted(list(frame_ids)), 'wkt': wkt}), 200, DEFAULT_HEADERS
