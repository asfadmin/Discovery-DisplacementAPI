import logging
import os
from typing import Optional
from fastapi import HTTPException
import fsspec
import numpy as np
import rasterio
import xarray as xr
import numpy.typing as npt
import io
from PIL import Image

# from fsspec.implementations.local import S3FileSystem
from s3fs.core import S3FileSystem

from src.models import FsspecParams

cwd = os.getcwd()
test_path = os.path.join(cwd, 'tests')
datasets_path = os.path.join(test_path, './sample_products')


def open_dataset(file_name: str, group: Optional[str] = None) -> xr.Dataset:
    # https://docs.aws.amazon.com/sdk-for-go/api/aws/credentials/endpointcreds/
    s3 = S3FileSystem()
    p = FsspecParams().model_dump()
    fsspec_file = s3.open(file_name, **p)
    try:
        logging.debug(
            msg=f'Reading "{file_name}"{"" if group is None else "Group: " + group} into dataset'
        )
        # https://filesystem-spec.readthedocs.io/en/latest/
        # https://docs.xarray.dev/en/stable/user-guide/io.html#cloud-storage-buckets
        data = xr.open_dataset(
            fsspec_file,  # type: ignore
            group=group,
            engine='h5netcdf',
            chunks={},
        )
    except Exception as e:
        raise HTTPException(400, f'Failed to read field name {file_name}: {e}')

    logging.debug(msg=f'"{file_name}" read into dataset!')
    return data


def open_zarr_store(
    file_system: S3FileSystem, target_files: list[str] = [], group='/'
) -> xr.Dataset:
    # Implements example from Luis López using fsspec_params and driver_config for kerchunked zarr store
    # https://gist.github.com/betolink/b545c364f80882c113b8cc27b763c729

    m = file_system.get_mapper('')

    dataset = xr.open_dataset(
        m,  # type: ignore
        engine='zarr',
        backend_kwargs={'consolidated': False, 'group': group},
        chunks={},
    )

    # https://github.com/pydata/xarray/issues/3124
    # Zarr stack is indexed by source_file_name. we can use this to pre-filter results to products
    # we're interested in
    if len(target_files):
        dataset = dataset.where(dataset.source_file_name.isin(target_files), drop=True)

    return dataset


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


def read_layer_as_png_buffer(file_name: str, layer: str) -> io.BytesIO:
    data = open_dataset(file_name=file_name)
    formatted = np.array(data[layer][:], dtype=np.float32)
    logging.debug(msg=f'"{layer}" layer read from "{file_name}", layer shape: {formatted.shape}')

    formatted = 255.0 * _normalize(formatted)
    img = Image.fromarray(formatted)
    img = img.convert('RGB')

    mask = np.invert(np.isnan(formatted)).astype(np.float32) * 255.0
    mask_image = Image.fromarray(mask)
    mask_image = mask_image.convert('L')
    img.putalpha(mask_image)

    io_buffer = io.BytesIO()

    logging.debug(msg='writing layer to bytes buffer as jpeg')
    img.save(io_buffer, format='png')
    logging.debug(msg='layer written to buffer!')

    return io_buffer


def get_wkt_from_dataset(
    data: xr.Dataset | xr.DataArray, identification: xr.Dataset | xr.DataArray
):
    wkt = str(identification.variables['bounding_polygon'].data)
    epsg = str(get_crs(data).to_epsg())
    logging.debug(msg=f'Got epsg {epsg} from crs')

    return {'wkt': wkt, 'epsg': epsg}


def get_crs(data):
    logging.debug(msg='Reading crs')
    spatial_ref = data.variables['spatial_ref']
    crs = rasterio.crs.CRS.from_string(spatial_ref.attrs['crs_wkt'])  # type: ignore
    logging.debug(msg=f'Read crs from data: {str(crs)}')
    return crs


def _normalize(data: npt.NDArray) -> npt.NDArray:
    lower = np.nanmin(data)
    ptp = np.nanmax(data) - lower

    # normalize
    return (data - lower) / ptp
