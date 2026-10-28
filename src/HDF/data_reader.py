import rasterio
import xarray as xr

from s3fs.core import S3FileSystem

from src import api_logger


def open_zarr_store(file_system: S3FileSystem, group='/') -> xr.Dataset:
    # Implements example from Luis López using fsspec_params and driver_config for kerchunked zarr store
    # https://gist.github.com/betolink/b545c364f80882c113b8cc27b763c729

    m = file_system.get_mapper('')
    return xr.open_dataset(
        m,  # type: ignore
        engine='zarr',
        backend_kwargs={'consolidated': False, 'group': group},
    )


def get_crs(data):
    api_logger.debug(msg='Reading crs')
    spatial_ref = data.variables['spatial_ref']
    crs = rasterio.crs.CRS.from_string(spatial_ref.attrs['crs_wkt'])  # type: ignore
    api_logger.debug(msg=f'Read crs from data: {crs!s}')
    return crs
