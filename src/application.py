import json
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Response

import logging

from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# from mangum import Mangum
from pydantic import BaseModel
from src.HDF.data_reader import kerchunkify_file, kerchunkify_stack
from src.models import (
    FsspecParams,
    KerchunkFileModel,
    KerchunkStackModel,
    TimeSeriesModel,
    WKTModel,
)
from src.timeseries import get_timeseries_at_pixel, layer_types
from src.HDF import read_layer_as_png_buffer
import s3fs
import ujson

import asf_search as asf
from . import log_router

router = APIRouter(route_class=log_router.LoggingRoute)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        '*'
    ],
    allow_methods=["*"],
    allow_headers=["*"],
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
            'wkt': 'POLYGON ((-120.6596489990334 38.10046393341369, -120.7165475579197 38.10851198053945, -120.766930740861 38.11562044217759, -120.8205210213509 38.12315205210022, -120.8714495693995 38.13028813229113, -120.9237420515751 38.13758904376237, -120.9763848233747 38.14491322663075, -121.0284993874585 38.15213949038783, -121.0805374061872 38.15933042899581, -121.1317842372317 38.16638876359664, -121.1831324092139 38.17343685331883, -121.2343267090171 38.1804400907544, -121.2851343767767 38.18736716519965, -121.3356959243903 38.19423758535788, -121.3861081098637 38.20106467487116, -121.4362721727969 38.20783544395677, -121.48323466170885 38.21415300334824, -121.4961042842803 38.15636388218255, -121.5433137463578 38.16270254678292, -121.5911446754841 38.1691031129965, -121.6386899947014 38.17544523556456, -121.6861407154369 38.18175427917799, -121.7332794261246 38.18800202289999, -121.7803915044837 38.19422601057961, -121.827141292521 38.20038272861196, -121.8737037166488 38.20649520761842, -121.9200946535652 38.21256588219698, -121.9662943385527 38.21859236147657, -122.0122835841423 38.22457236130022, -122.0581361973249 38.23051573928061, -122.1041763492786 38.23646390681441, -122.149693424194 38.24232638029159, -122.1961235981019 38.24828575950047, -122.242840340764 38.25426186141181, -122.2851111656349 38.25965821461571, -122.3300033441712 38.2653676014464, -122.3758025278513 38.27117216227268, -122.4195396691845 38.27670031010642, -122.3858453485523 38.44296136955153, -122.3532454174394 38.60872264056508, -122.321281901071 38.77481263179438, -122.2870678391941 38.9402423639722, -122.28657198358258 38.94018057384403, -122.2484647545139 39.10551216594683, -122.2139845790114 39.27116104878576, -122.1797260176706 39.4367089374228, -122.1454462898122 39.60250573468526, -122.1112187045845 39.76830723022915, -122.0657227757032 39.76272908715357, -122.0199986201785 39.75710391072595, -121.974167995761 39.75144665647245, -121.9280106375743 39.74573006489359, -121.8819129486135 39.74000139035989, -121.8355618840318 39.73422190999039, -121.7893509902118 39.72844019721962, -121.7438269303752 39.72272426697831, -121.6969816389773 39.71682457472104, -121.6515073229837 39.71107635608378, -121.6043191954164 39.70509395348859, -121.5584565168173 39.69925815820748, -121.5109102827927 39.69319018010273, -121.4645931051444 39.68725740118437, -121.4191841855194 39.68142061388765, -121.3710837028612 39.67522101887367, -121.3249639873766 39.66925411189222, -121.2737070377029 39.66260665395009, -121.23414991223851 39.657450537553174, -121.2225423730193 39.71501508524592, -121.1765350243167 39.70900995464177, -121.1256787673412 39.70235510426308, -121.0761429466098 39.6958485542612, -121.0248065795119 39.68908396631235, -120.9731471040036 39.68225266837984, -120.9238122923641 39.67570292460091, -120.8690679290765 39.66841567043333, -120.8147668765373 39.66115958039808, -120.7685909543843 39.65495848719279, -120.7156528937689 39.64783419415447, -120.663007754518 39.64072322969391, -120.6113623558398 39.6337213126097, -120.5575229174151 39.62639828522865, -120.4998084040708 39.61852276683964, -120.4452699517613 39.61104894626836, -120.3863396198317 39.60294709422497, -120.3350203072667 39.59585767211257, -120.2794058786818 39.5881523754319, -120.2276117469398 39.58094649107327, -120.22744443645614 39.58092314818873, -120.2134545404021 39.63753782618391, -120.1722737074452 39.6317932200585, -120.1244336159495 39.62510726553644, -120.0702567931258 39.61751657755807, -120.022269227435 39.61076456269333, -119.9734628265665 39.60387622000747, -119.9205724742573 39.59639065119934, -119.8710716027977 39.58935798135493, -119.8176837356334 39.58175135017377, -119.7678667295637 39.57462631850627, -119.7172666919774 39.56736632596481, -119.6677829890141 39.56024234859523, -119.6164294368659 39.55282685903347, -119.5655855530352 39.54546030402012, -119.5122825240406 39.53771380091477, -119.4596714762434 39.53004121358733, -119.4118356441431 39.52303826133494, -119.3539548115401 39.51454620335684, -119.2999598520621 39.50659276685604, -119.242172282983 39.49805375475951, -119.1867112941332 39.48982722325655, -119.2279582300632 39.32389259181299, -119.2695651047809 39.15814430461985, -119.3154157605841 38.99290396440068, -119.3553955782568 38.82692456194625, -119.4076391719693 38.66278010421749, -119.46426202130762 38.48267405863559, -119.4994803127931 38.33275776186966, -119.5473964124392 38.1679932576986, -119.5759619696445 38.00032674732519, -119.6328594358995 38.00892055228446, -119.685940538886 38.01691396436385, -119.735510021753 38.02435806698762, -119.7876843769492 38.0321663403309, -119.8349767585424 38.03922663419335, -119.8827140678868 38.04633197874039, -119.9336830819589 38.05389196505576, -119.9837372437618 38.06129369064131, -120.029196677421 38.0680003062205, -120.0790441003354 38.07532784287181, -120.1269111066452 38.08234457142717, -120.1767641224129 38.08962794955193, -120.2211977375846 38.09610549717873, -120.2696883291999 38.10314938009251, -120.3131576383198 38.10945036625376, -120.3570069870991 38.11578848698885, -120.4046282389668 38.12264764067351, -120.4517936234199 38.12942103705984, -120.48468630063608 38.134130553754865, -120.4964144795629 38.07720256883281, -120.5521610008301 38.08517268978709, -120.6049996926634 38.09270374285773, -120.6596489990334 38.10046393341369))',
        },
        headers=DEFAULT_HEADERS,
    )


@app.post(
    '/timeseries',
    description='Returns a json response with values read at "unwrapped_phase", "interferometric_correlation", and "temporal_coherence" layers in provided files at given point',
)
def get_timeseries(series: TimeSeriesModel):
    # epsg: 32610
    lat = series.lat
    lon = series.lon
    file_store = series.file_store

    logging.debug(f'Sampling timeseries at lat {lat}, lon {lon}')
    if series.fsspec_params is None:
        series.fsspec_params = FsspecParams()

    try:
        output_str = get_timeseries_at_pixel(
            lat=lat, lon=lon, file_store=file_store, fsspec_params=series.fsspec_params
        )
    except BaseException as exc:
        raise HTTPException(
            500, detail=f'Failed to calculate timeseries. Original Exception: {exc}'
        )

    return Response(content=output_str, media_type='application/json', headers=DEFAULT_HEADERS)


@app.post(
    '/kerchunk_stack',
    description='Returns a json zarr store bytes',
)
def kerchunk_stack(KerchunkArgs: KerchunkStackModel):
    try:
        bytes_output = kerchunkify_stack(KerchunkArgs.files)
    except BaseException as exc:
        raise HTTPException(
            500,
            detail=f'Failed to kerchunkify the provided stack of files. Original Exception: {exc}',
        )

    destination_bucket = KerchunkArgs.destination_bucket
    filename = '11114.json'

    s3 = s3fs.S3FileSystem()
    try:
        destination = f'{destination_bucket}{filename}'
        with s3.open(destination, 'wb') as f:
            f.write(bytes_output)  # type: ignore
    except HTTPException as e:
        raise e
    except BaseException as e:
        raise HTTPException(
            500,
            detail=f'Failed to write zarr store to destination {destination}. Original Exception: {e}',
        )

    return Response(
        content=ujson.dumps({'file_uri': destination}),
        headers=DEFAULT_HEADERS,
        media_type='application/json',
    )


@app.post(
    '/kerchunk_file',
    description='Returns a json zarr store bytes',
)
def kerchunk_file(KerchunkArgs: KerchunkFileModel):
    s3_str = KerchunkArgs.file_uri.unicode_string()
    destination_str = KerchunkArgs.destination.unicode_string()
    s3 = s3fs.S3FileSystem()
    try:
        zarr_store = kerchunkify_file(s3_str, s3_file_system=s3)
    except BaseException as exc:
        raise HTTPException(
            500,
            detail=f'Failed to kerchunkify the provided file. Original Exception: {exc}',
        )

    if KerchunkArgs.destination_filename is None:
        destination = f'{destination_str}{Path(s3_str).name}.json'
    else:
        destination = f'{destination_str}{KerchunkArgs.destination_filename}'
        if not destination.endswith('.json'):
            destination += '.json'

    try:
        with s3.open(destination, 'wb') as f:
            f.write(zarr_store)  # type: ignore
    except BaseException as e:
        raise HTTPException(
            500,
            detail=f'Failed to write zarr store to destination {destination}. Original Exception: {e}',
        )

    return Response(
        content=ujson.dumps({'file_uri': destination}),
        headers=DEFAULT_HEADERS,
        media_type='application/json',
    )


@app.post(
    '/get_frame_id',
    description='Returns a json zarr store bytes',
)
def get_frame_ids(wkt_event: WKTModel):
    wkt = wkt_event.wkt
    try:
        response = asf.search(intersectsWith=wkt, dataset=asf.DATASET.OPERA_S1, maxResults=250)
    except asf.ASFSearchError as exc:
        raise HTTPException(
            status_code=500, detail=f'Failed to find frame(s) for given wkt. Reason: {exc}'
        )

    frame_ids = {
        burst_id
        for product in response
        if (burst_id := product.properties.get('operaBurstID')) is not None
    }

    if len(frame_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail=f'No OPERA-S1 burst frame ids were found over the given aoi: {wkt}',
        )

    return JSONResponse({'frame_ids': sorted(list(frame_ids)), 'wkt': wkt}, headers=DEFAULT_HEADERS)
