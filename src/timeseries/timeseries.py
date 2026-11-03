import re
from datetime import datetime, timedelta
from time import perf_counter

import fsspec
import fsspec.config
import numpy as np
import pandas
import xarray as xr
from pyproj import CRS, Transformer
from shapely import Point
from shapely.geometry.base import BaseGeometry

from src import api_logger
from src.constants import fsspec_params
from src.exceptions import NaNAOIException, OutdatedStackException
from src.HDF.data_reader import get_crs, open_zarr_store

_data_variables = [
    'netcdf_uri',
    'bytes',
    'reference_datetime',
    'secondary_datetime',
    'temporal_baseline',
    'short_wavelength_displacement',
]


def get_timeseries_over_aoi(
    geometry: BaseGeometry,
    wrapped_geometry: BaseGeometry,
    file_store: str,
) -> str:
    start = perf_counter()

    try:
        fs = fsspec.filesystem(
            'reference',
            fo=file_store,
            remote_protocol='s3',
            target_options={'compression': 'gzip'},
            remote_options={
                'anon': False,
                'default_fill_cache': False,
                'skip_instance_cache': False,
                **fsspec_params,
            },
        )

    except Exception as exc:
        api_logger.error(f'Failed to open file. Original Error: {exc}')
        raise
    api_logger.info(f's3fs filesystem creation: {perf_counter() - start} seconds')

    start = perf_counter()
    values = open_zarr_store(file_system=fs)
    api_logger.info(f'Remote dataset opened: {perf_counter() - start} seconds')

    pre_filter_count = len(values.source_file_name)
    values = _latest_product_versions(values)
    values = _minimum_version(values)
    post_filter_count = len(values.source_file_name)

    api_logger.info(
        f'Filtered {pre_filter_count - post_filter_count} duplicate/old products from stack.'
    )

    if post_filter_count == 0:
        raise OutdatedStackException(
            status_code=400,
            detail=f'No V1.0+ products found in stack "{file_store.split("/")[-1]}"',
        )

    start = perf_counter()
    _calc_temporal_offsets(values)
    api_logger.info(f'Temporal Offset calc: {perf_counter() - start} seconds')

    start = perf_counter()
    if isinstance(wrapped_geometry, Point):
        values = _read_layers_at_pixel(values, lon=wrapped_geometry.x, lat=wrapped_geometry.y)
    api_logger.info(f'AOI Read Speed: {perf_counter() - start} seconds')
    return _pandas_output(values, wkt=geometry.wkt)


def _latest_product_versions(values: xr.Dataset) -> xr.Dataset:
    """Remove duplicate products by their secondary datetime, keeping the latest version"""
    secondary = values['secondary_datetime'].to_series().sort_values()
    latest = secondary.drop_duplicates(keep='last').index.values
    return values.sel(source_file_name=latest)


def _minimum_version(values: xr.Dataset) -> xr.Dataset:
    """Only keep products of minimum version `0.9` or above"""
    mask = values.coords['source_file_name'].str.match(r'.*(v1\..).*\.nc?')
    return values.isel(source_file_name=mask)


# https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset
# pass to pre-process
def _read_layers_at_pixel(dataset: xr.Dataset, lat: float, lon: float) -> xr.Dataset:
    # reprojects lon lat to dataset projection, returns dict with reading at each layer
    crs = get_crs(dataset)
    xx, yy = _to_crs(lat, lon, target_proj=crs.to_epsg())
    xx_index = np.abs(dataset.x.data - xx).argmin()
    yy_index = np.abs(dataset.y.data - yy).argmin()

    return dataset[_data_variables].isel(x=xx_index, y=yy_index)


def _to_crs(lat: float, lon: float, source_proj='4326', target_proj='32610'):
    source_crs = CRS.from_epsg(source_proj)
    target_crs = CRS.from_epsg(target_proj)

    source_to_target = Transformer.from_crs(source_crs, target_crs)
    return source_to_target.transform(lat, lon)


def _calc_temporal_offsets(data: xr.Dataset):
    """Returns reference times and calculated temporal offset based off earliest reference_datetime value"""
    secondary_datetimes = data['secondary_datetime']
    reference_datetimes = data['reference_datetime']

    data['temporal_baseline'] = (
        (secondary_datetimes.dt.date - reference_datetimes.dt.date.min())
        .astype('timedelta64[s]')
        .dt.days
    )


def _within_one_day(date1: datetime, date2: datetime) -> bool:
    return abs(date1 - date2) <= timedelta(days=1)


def _fix_rolling_reference(data: pandas.DataFrame) -> pandas.DataFrame:
    # doing this in xarray was REALLY slow (possibly do to dask eval on each individual timestep, ~0.2-0.4s each)
    # performing fix with pandas dataframe significantly more performant

    # grab the first scene, use to offset first timestep to 0
    prev_granule = data.iloc[0]
    correction = 0

    start = perf_counter()
    for _, scene in data.iterrows():
        # apply last scene with previous reference date as offset
        if not _within_one_day(scene.reference_datetime, prev_granule.reference_datetime):
            correction += prev_granule.short_wavelength_displacement

        data.loc[scene.name, 'short_wavelength_displacement'] += correction
        prev_granule = scene

    # update reference dates
    for _, scene in data.iterrows():
        data.loc[scene.name, 'reference_datetime'] = data.iloc[0].reference_datetime

    api_logger.info(
        f'Rolling reference correction for {len(data)}: {perf_counter() - start} seconds'
    )

    return data


def _pandas_output(data: xr.Dataset, wkt: str):
    start = perf_counter()
    data = data.sortby('secondary_datetime')
    try:
        pandas_values = data.to_pandas()
    except Exception as e:
        print(e)
        raise
    nans = pandas_values['short_wavelength_displacement'].isna()

    if len(pandas_values[~nans]) == 0:
        raise NaNAOIException(400, detail=f'No data exists for wkt "{wkt}"')

    pandas_values['short_wavelength_displacement'] = pandas_values[
        'short_wavelength_displacement'
    ].fillna(0)
    pandas_values = _fix_rolling_reference(pandas_values)

    pandas_values = pandas_values.reset_index().set_index('source_file_name')
    file_name = str(pandas_values.iloc[0].name)
    frame_name = re.search(r'.*_(F[1-9]*)_.*', file_name)
    if frame_name and len(frame_name.groups()):
        pandas_values['frame'] = np.full(len(pandas_values), frame_name.group(1))

    pandas_values.loc['mean'] = pandas_values[~nans].mean(skipna=True, numeric_only=True)
    pandas_values['is_masked'] = nans.astype(bool)
    out = pandas_values.to_json(date_format='iso', orient='index')
    api_logger.info(f'Pandas conversion: {perf_counter() - start} seconds')
    return out
