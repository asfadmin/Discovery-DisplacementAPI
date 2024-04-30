import logging
import os
from fastapi import HTTPException
import numpy as np
import rasterio
import xarray as xr
import numpy.typing as npt

import io
from PIL import Image
# from fsspec.implementations.local import S3FileSystem
from s3fs.core import S3FileSystem
cwd = os.getcwd()
test_path = os.path.join(cwd, 'tests')
datasets_path = os.path.join(test_path, "./sample_products")

def open_dataset(file_name: str, group: str = None) -> xr.Dataset:
    # https://docs.aws.amazon.com/sdk-for-go/api/aws/credentials/endpointcreds/
    s3 = S3FileSystem()
    fsspec_file = s3.open(file_name)
    try:
        logging.debug(msg=f'Reading "{file_name}"{"" if group is None else "Group: " + group} into dataset')
        # https://filesystem-spec.readthedocs.io/en/latest/
        # https://docs.xarray.dev/en/stable/user-guide/io.html#cloud-storage-buckets
        data = xr.open_dataset(fsspec_file,group=group,
    # backend_kwargs={
    #     "storage_options": {"project": "<project-name>", "token": None}
    # },
    engine="h5netcdf",
    )
    except Exception as e:
        raise HTTPException(400, f"Failed to read field name {file_name}: {e}")
    
    logging.debug(msg=f'"{file_name}" read into dataset!')
    return data

def open_datasets(file_names: str, group: str = None, preprocess: callable = None) -> xr.Dataset:
    s3 = S3FileSystem()
    fsspec_files = [s3.open(file_name) for file_name in file_names]
    datasets = xr.open_mfdataset(fsspec_files,combine="by_coords", coords='all', engine="h5netcdf", preprocess=preprocess)
    return datasets

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

    logging.debug(msg=f'"writing layer to bytes buffer as jpeg')
    img.save(io_buffer, format="png")
    logging.debug(msg=f'"layer written to buffer!')
    
    return io_buffer

def get_wkt_from_dataset(data: xr.DataArray, identification: xr.DataArray):
    wkt = str(identification.variables['bounding_polygon'].data)
    epsg = str(get_crs(data).to_epsg())
    logging.debug(msg=f"Got epsg {epsg} from crs")

    return {'wkt': wkt, 'epsg': epsg}

def get_crs(data):
    logging.debug(msg=f'Reading crs')
    spatial_ref = data.variables['spatial_ref']
    crs = rasterio.crs.CRS.from_string(spatial_ref.attrs['crs_wkt'])
    logging.debug(msg=f'Read crs from data: {str(crs)}')
    return crs

def _normalize(data: npt.NDArray) -> npt.NDArray:
    lower = np.nanmin(data)
    ptp = np.nanmax(data) - lower
    
    # normalize
    return (data - lower) / ptp