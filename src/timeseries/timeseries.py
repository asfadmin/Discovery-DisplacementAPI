# import rasterio
from typing import Tuple
import fsspec
from shapely import LineString, Point, Polygon
from src.HDF.data_reader import open_zarr_store, get_crs
from pyproj import CRS, Transformer
import xarray as xr
from src.models import FsspecParams
from shapely.ops import transform as shapely_transform
from shapely.geometry.base import BaseGeometry
import geopandas as gpd
# from pandas import DataFrame

layer_types = [
    'unwrapped_phase',
    'interferometric_correlation',
    'temporal_coherence',
    'persistent_scatterer_mask',
]

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
    target_files: list[str],
    fsspec_params: FsspecParams,
) -> str:
    fs = fsspec.filesystem(
        'reference',
        fo=file_store,
        remote_protocol='s3',
        remote_options={
            'anon': False,
            'default_fill_cache': False,
            'skip_instance_cache': False,
            **fsspec_params.model_dump(),
        },
    )
    values = open_zarr_store(
        file_system=fs,
        target_files=target_files,
    )
    # identification = open_zarr_store(
    #     file_system=fs,
    #     target_files=target_files,
    #     group='identification',
    # )
    _calc_temporal_offsets(values)

    if isinstance(geometry, Point):
        values = _read_layers_at_pixel(values, lon=geometry.x, lat=geometry.y)
    elif isinstance(geometry, Polygon) or isinstance(geometry, LineString):
        values = _read_layers_with_aoi(values, geometry)
    return _pandas_output(values)


# https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset
# pass to pre-process
def _read_layers_at_pixel(dataset: xr.Dataset, lat: float, lon: float) -> xr.Dataset:
    # reprojects lon lat to dataset projection, returns dict with reading at each layer
    crs = get_crs(dataset)
    xx, yy = _to_crs(lat, lon, target_proj=crs.to_epsg())
    return dataset[_data_variables].sel(x=xx, y=yy, method='nearest')


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
    print(gdf)
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


def _calc_temporal_offsets(data: xr.Dataset) -> Tuple[xr.DataArray, xr.DataArray]:
    """Returns reference times and calculated temporal offset based off earliest reference_datetime value"""
    secondary_datetimes = data['secondary_datetime']
    reference_datetimes = data['reference_datetime']

    data['temporal_baseline'] = (
        (secondary_datetimes.dt.date - reference_datetimes.dt.date.min())
        .astype('timedelta64[s]')
        .dt.days
    )
    # return reference_datetimes, temporal_baselines


def _pandas_output(data: xr.Dataset):
    pandas_values = data.to_pandas()
    pandas_values = pandas_values.assign(
        file_name=pandas_values['netcdf_uri'].map(lambda uri: uri.split('/')[-1])
    )

    # sort by time, make fileName column the index for our data for nicer json output
    pandas_values = pandas_values.sort_index().reset_index().set_index('file_name')
    pandas_values.loc['mean'] = pandas_values.mean(skipna=True, numeric_only=True)
    return pandas_values.to_json(date_format='iso', orient='index')
