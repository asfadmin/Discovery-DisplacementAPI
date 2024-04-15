import logging
import os
from fastapi import HTTPException
import numpy as np
import rasterio
import xarray as xr
import numpy.typing as npt

import io
from PIL import Image


cwd = os.getcwd()
test_path = os.path.join(cwd, 'tests')
datasets_path = os.path.join(test_path, "./sample_products")

def open_dataset(file_name: str, group: str = None) -> xr.Dataset:
    try:
        logging.debug(msg=f'Reading "{file_name}"{"" if group is None else "Group: " + group} into dataset')
        data = xr.open_dataset(os.path.join(datasets_path, file_name),group=group)
    except Exception as e:
        raise HTTPException(400, f"Failed to read field name {file_name}: {e}")
    
    logging.debug(msg=f'"{file_name}" read into dataset!')
    return data

def read_layer_as_png_buffer(file_name: str, layer: str) -> io.BytesIO:
    data = open_dataset(file_name=file_name)
    formatted = np.array(data[layer][:], dtype=np.float32)
    logging.debug(msg=f'"{layer}" layer read from "{file_name}", layer shape: {formatted.shape}')
    
    normalized_layer = _normalize(formatted)
    img = Image.fromarray(normalized_layer, mode="F")
    img = img.convert('RGBA')
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
    return 255.0 * ((data - lower) / ptp)