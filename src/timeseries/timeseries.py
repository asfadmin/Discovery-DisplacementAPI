# import rasterio
from datetime import datetime, timedelta
import fsspec
import fsspec.config
import numpy as np
from shapely import LineString, Point, Polygon
from src.HDF.data_reader import open_zarr_store, get_crs
from pyproj import CRS, Transformer
import xarray as xr
from src.constants import fsspec_params
from shapely.ops import transform as shapely_transform
from shapely.geometry.base import BaseGeometry
import geopandas as gpd
import pandas
from src import api_logger
from time import perf_counter

from src.exceptions import OutdatedStackException

layer_types = ['short_wavelength_displacement']

_data_variables = [
    *layer_types,
    'netcdf_uri',
    'bytes',
    'reference_datetime',
    'secondary_datetime',
    'temporal_baseline',
]


def get_timeseries_over_aoi(
    geometry: BaseGeometry,
    file_store: str,
) -> str:
    start = perf_counter()
    fs = fsspec.filesystem(
        'reference',
        fo=file_store,
        remote_protocol='s3',
        target_options=dict(compression='gzip'),
        remote_options={
            'anon': False,
            'default_fill_cache': False,
            'skip_instance_cache': False,
            **fsspec_params,
        },
    )
    api_logger.info(f's3fs filesystem creation: {perf_counter() - start} seconds')

    start = perf_counter()
    values = open_zarr_store(file_system=fs)
    api_logger.info(f'Remote dataset opened: {perf_counter() - start} seconds')

    pre_filter_count = len(values.source_file_name)
    values = _latest_product_versions(values)
    values = _minimum_version(values)
    post_filter_count = len(values.source_file_name)
    
    api_logger.info(f'Filtered {pre_filter_count-post_filter_count} duplicate/old products from stack.')

    if post_filter_count == 0:
        raise OutdatedStackException(status_code=502, detail=f'No V1.0+ products found in stack "{file_store.split("/")[-1]}"')
    
    start = perf_counter()
    _calc_temporal_offsets(values)
    api_logger.info(f'Temporal Offset calc: {perf_counter() - start} seconds')

    start = perf_counter()
    if isinstance(geometry, Point):
        values = _read_layers_at_pixel(values, lon=geometry.x, lat=geometry.y)
    elif isinstance(geometry, Polygon) or isinstance(geometry, LineString):
        values = _read_layers_with_aoi(values, geometry)
    api_logger.info(f'AOI Read Speed: {perf_counter() - start} seconds')
    return _pandas_output(values)

def _latest_product_versions(values: xr.Dataset) -> xr.Dataset:
    """Remove duplicate products by their secondary datetime, keeping the latest version"""
    secondary = values['secondary_datetime'].to_series().sort_values()
    latest = secondary.drop_duplicates(keep='last').index.values
    return values.sel(source_file_name=latest)

def _minimum_version(values: xr.Dataset) -> xr.Dataset:
    """Only keep products of minimum version `0.9` or above"""
    mask = values.coords['source_file_name'].str.match(r'.*((v1\..)|(v0\.9)).*\.nc?')
    return values.isel(source_file_name=mask)

# https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset
# pass to pre-process
def _read_layers_at_pixel(dataset: xr.Dataset, lat: float, lon: float) -> xr.Dataset:
    # reprojects lon lat to dataset projection, returns dict with reading at each layer
    crs = get_crs(dataset)
    xx, yy = _to_crs(lat, lon, target_proj=crs.to_epsg())
    xx_index = np.abs(dataset.x.data - xx).argmin()
    yy_index = np.abs(dataset.y.data - yy).argmin()
    # FIXME remove when no longer using old staged data
    important_variable = (
        'unwrapped_phase'
        if 'unwrapped_phase' in list(dataset.data_vars)
        else 'short_wavelength_displacement'
    )
    data_variables = [important_variable] + _data_variables
    return dataset[data_variables].isel(x=xx_index, y=yy_index)


def _read_layers_with_aoi(dataset: xr.Dataset, geometry: BaseGeometry):
    """
    Read a spatial subset from the stack with a reprojection of the provided geometry
    Returns the average values for each aoi at each timestep
    """
    crs = get_crs(dataset)
    epsg = crs.to_epsg()

    projected = _transform_geometry(geometry=geometry, target_proj=epsg)

    dataset.rio.set_spatial_dims(x_dim='x', y_dim='y', inplace=True)
    dataset.rio.write_crs(str(crs), inplace=True)

    d = {'col1': ['aoi'], 'geometry': [projected]}
    gdf = gpd.GeoDataFrame(d, crs=str(epsg))  # type: ignore

    # clip_box limits the clipped geometry to the aoi bounds,
    # otherwise rioxarray will load THE ENTIRE DATASET FOOTPRINT into memory.
    # Not a perfect solution, as any shape that isn't perfectly aligned with
    # bounding dimensions will lead to more remote reads than necessary
    # ex: the trianges between a bounding box and a rotated square will be
    # loaded by `clip()`

    # TODO: Explore opening only one frame, clipping it, then use those
    # indexes to read the remaining timesteps without loading the extra data
    # (assuming all data in uniformly alligned over a frame id, which should be the case)
    clipped_box = dataset.rio.clip_box(*projected.bounds)
    output = clipped_box.rio.clip(gdf.geometry.values, gdf.crs, drop=True)
    return output.mean(['x', 'y'])


def _to_crs(lat: float, lon: float, source_proj='4326', target_proj='32610'):
    source_crs = CRS.from_epsg(source_proj)
    target_crs = CRS.from_epsg(target_proj)

    source_to_target = Transformer.from_crs(source_crs, target_crs)
    return source_to_target.transform(lat, lon)


def _transform_geometry(geometry: BaseGeometry, source_proj='4326', target_proj='32610'):
    project = Transformer.from_crs(source_proj, target_proj, always_xy=True).transform
    return shapely_transform(project, geometry)


# def _drop_min_version(data: xr.Dataset):
#     return data.where(lambda scene: float(scene.product_version[1:]) >= 0.9)


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
    correction = -prev_granule.short_wavelength_displacement

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


def _pandas_output(data: xr.Dataset):
    start = perf_counter()
    data = data.sortby('secondary_datetime')
    pandas_values = data.to_dataframe()
    pandas_values = _fix_rolling_reference(pandas_values)
    
    pandas_values = pandas_values.reset_index().set_index('source_file_name')
    pandas_values.loc['mean'] = pandas_values.mean(skipna=True, numeric_only=True)
    out = pandas_values.to_json(date_format='iso', orient='index')
    api_logger.info(f'Pandas conversion: {perf_counter() - start} seconds')
    return out
    