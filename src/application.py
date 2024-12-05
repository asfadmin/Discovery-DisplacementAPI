import json
from flask import Blueprint, jsonify, request, Response
from pathlib import Path

from src.models import (
    FsspecParams,
    TimeSeriesModel,
)
from src.timeseries import layer_types, get_timeseries_over_aoi
from src.HDF import read_layer_as_png_buffer

import s3fs
import geopandas as gpd
from shapely import wkt as shapely_wkt


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
        'wkt': 'POLYGON ((-149.451139279365 62.1287442968912, -149.489207371942 62.045616952959, -149.476221395717 62.0129791068178, -149.519088628246 61.955889388159, -149.536405309494 61.854259222719, -149.586547633797 61.725062981579, -149.594933718237 61.6491856726608, -149.81365221469 60.9678772131571, -149.835750622071 60.9420795477735, -149.859662107215 60.8380786660427, -149.904017634358 60.7487221866998, -149.925244567858 60.643143005989, -148.495889771202 60.5277410743715, -148.470041402483 60.584602367533, -146.906606463731 60.4396563701975, -146.873685244838 60.4951172124558, -145.386267125578 60.3396641673686, -145.290423628369 60.5402632158137, -145.280500106703 60.5829732084687, -145.301225650796 60.5845853001108, -145.236822870895 60.6909796637016, -145.247262492305 60.7010850131082, -145.224251585634 60.7495463006203, -145.232581050756 60.7682458705588, -145.187153890321 60.8021251581012, -145.208019152527 60.8234194914492, -145.058111527729 61.0387595374364, -145.099374030659 61.0732930019398, -145.024138665138 61.1204393557309, -145.047326954518 61.1417906129957, -145.030470686787 61.1886939957555, -144.963180408383 61.2453544268513, -144.984671478238 61.2677677145688, -144.976235627719 61.337959599446, -144.89834894171 61.4289187444297, -144.910469614585 61.4579328980322, -144.890927390867 61.4721803217938, -144.897062103683 61.4897872096134, -144.874529671332 61.5309281203528, -144.843140879426 61.5522585942678, -144.843705014899 61.5929497163114, -144.762933706766 61.6622405486587, -144.700945264316 61.8174811273622, -146.289453228815 61.9803053628305, -146.329597119308 61.9247592198443, -147.983354118586 62.073430473257, -148.010743582664 62.0164065972356, -149.451139279365 62.1287442968912))'
    }), 200, DEFAULT_HEADERS


@api_blueprint.route('/timeseries', methods=['POST'])
def get_timeseries():
    """Returns a json response with values read at `unwrapped_phase`,
      `interferometric_correlation`, and `temporal_coherence` layers in provided files at given point."""
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
    try:
        wkt = data.get('wkt')
        geometry = shapely_wkt.loads(wkt)

        frame_path = Path(__file__).parent.parent / 'data' / 'frames.geojson'
        gdf = gpd.read_file(frame_path, engine='pyogrio')
        result = gdf[gdf.intersects(geometry)]
        frame_ids = set(result['frame_id'])

    except Exception as exc:
        return jsonify({'error': f'Failed to load WKT. Error: {exc}'}), 400

    if not frame_ids:
        return jsonify({'error': f'No OPERA-S1 burst frame IDs were found for the given AOI: {wkt}'}), 400

    return jsonify({'frame_ids': sorted(list(frame_ids)), 'wkt': wkt}), 200, DEFAULT_HEADERS
