import logging
import fsspec
import rasterio
import xarray as xr
from src import api_logger
# from fsspec.implementations.local import S3FileSystem
from s3fs.core import S3FileSystem
from time import perf_counter

def open_zarr_store(file_system: S3FileSystem, group='/') -> xr.Dataset:
    # Implements example from Luis López using fsspec_params and driver_config for kerchunked zarr store
    # https://gist.github.com/betolink/b545c364f80882c113b8cc27b763c729
    return xr.open_dataset(
        file_system.get_mapper(''),  # type: ignore
        engine='zarr',
        backend_kwargs={'consolidated': False, 'group': group},
    )

def get_bounding_polygon(file_uri: str):
    fs = fsspec.filesystem(
        'reference',
        **{
            'fo': file_uri,
            'remote_protocol': 's3',
            'compression': 'gzip',
            'remote_options': {'anon': False},
        },
        # One line required to specify compression here
        target_options={'compression': 'gzip'},
    )
    identity = xr.open_dataset(
        fs.get_mapper(), engine='zarr', consolidated=False, group='identification'
    )
    return identity['bounding_polygon'][0].item().decode()


def get_wkt_from_dataset(
    data: xr.Dataset | xr.DataArray, identification: xr.Dataset | xr.DataArray
):
    wkt = str(identification.variables['bounding_polygon'].data)
    epsg = str(get_crs(data).to_epsg())
    api_logger.debug(msg=f'Got epsg {epsg} from crs')

    return {'wkt': wkt, 'epsg': epsg}


def get_crs(data):
    api_logger.debug(msg='Reading crs')
    spatial_ref = data.variables['spatial_ref']
    crs = rasterio.crs.CRS.from_string(spatial_ref.attrs['crs_wkt'])  # type: ignore
    api_logger.debug(msg=f'Read crs from data: {str(crs)}')
    return crs
