import logging
import os
from typing import Optional, Tuple
from fastapi import HTTPException
import fsspec
import numpy as np
import rasterio
import xarray as xr
import numpy.typing as npt
import zarr
from pathlib import Path

import ujson
import io
from PIL import Image

# from fsspec.implementations.local import S3FileSystem
from s3fs.core import S3FileSystem
import zarr.hierarchy

from src.models import DriverKeywords, FsspecParams
from kerchunk.hdf import SingleHdf5ToZarr
from kerchunk.combine import MultiZarrToZarr

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
            driver_kwds=DriverKeywords().model_dump(),
        )
    except Exception as e:
        raise HTTPException(400, f'Failed to read field name {file_name}: {e}')

    logging.debug(msg=f'"{file_name}" read into dataset!')
    return data


def open_zarr_store(
    file_store: str,
    fsspec_params: FsspecParams,
    driver_params: DriverKeywords,
) -> xr.Dataset:
    # s3 = S3FileSystem()

    # Implements example from Luis López using fsspec_params and driver_config for kerchunked zarr store
    # https://gist.github.com/betolink/b545c364f80882c113b8cc27b763c729

    # bucket = '/'.join(file_store.split('/')[:-1])
    fs = fsspec.filesystem(
        'reference',
        fo=file_store,
        remote_protocol='s3',
        remote_options={
            'anon': False,
            'default_fill_cache': False,
            'default_cache_type': 'blockcache',
            'skip_instance_cache': True,
            'default_block_size': 24 * 1024 * 1024,
            # 'block_size': 24 * 24,
        },
    )
    m = fs.get_mapper('')

    dataset = xr.open_dataset(
        m, engine='zarr', backend_kwargs={'consolidated': False}, chunks={}
    )
    # dataset['file_name'] = dataset['file_name'].astype('unicode')
    # s3_files = [f'{bucket}/{fe.item()}' for fe in dataset['file_name']]
    # I    dataset =dataset.drop('file_name')
    # dataset['sizes'] = s3.sizes(s3_files)

    # )

    return dataset


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


def kerchunkify_stack(uris: list[str]) -> bytes:
    # s3 = S3FileSystem()
    # file_names = []
    # local_file_system = fsspec.filesystem('')
    # for uri in uris:

    # h5_str = kerchunkify_file(file_uri=uri, s3_file_system=s3)
    # outf = f'{pathlib.Path(uri).name}.json'
    # with local_file_system.open(outf, 'wb') as f:
    #     f.write(h5_str)
    # file_names.append(outf)

    return _merge_kerchunks(uris)


def kerchunkify_file(
    file_uri: str,
    s3_file_system: S3FileSystem = S3FileSystem(),
    storage_options: dict = {
        'mode': 'rb',
        'anon': False,
        'default_fill_cache': False,
        'default_cache_type': 'first',
        'default_block_size': 1024 * 1024,
    },
) -> bytes:
    with s3_file_system.open(file_uri, **storage_options) as infile:
        h5chunks = SingleHdf5ToZarr(infile, file_uri, inline_threshold=300) # type: ignore (infile)

        file_size = infile.size # type: ignore (infline.size)
        
        # store uri and size of file at time of writing zarr store
        zarr_store = zarr.hierarchy.open_group(h5chunks.store)
        zarr_store.create_dataset('uri', data=file_uri, dtype=str)
        zarr_store.create_dataset('bytes', data=file_size, dtype=float)
        return ujson.dumps(h5chunks.translate()).encode()


def _merge_kerchunks(
    files: list[str],
    storage_options: dict = {
        'mode': 'rb',
        'anon': False,
        'default_fill_cache': False,
        'default_cache_type': 'first',
        'block_size': 24 * 1024 * 1024,
    },
) -> bytes:
    # import re

    # ex = re.compile(r'.*/(.*).json')
    mzz = MultiZarrToZarr(
        files,
        target_options=storage_options,
        # remote_protocol='s3',
        concat_dims=['time'],
        identical_dims=['y', 'x'],
        # variables=
        coo_map={
            'time': 'cf:time',  # THIS KEEPS TIME FROM BEING DROPPED:
        },  # https://github.com/fsspec/kerchunk/issues/343#issuecomment-1666289741
    )

    d = mzz.translate()

    return ujson.dumps(d).encode()
