from functools import partial
import logging
import math
from typing import Optional

import numpy as np
# import rasterio
from src.HDF.data_reader import open_dataset, open_datasets, get_crs
from pyproj import CRS, Transformer
import xarray as xr

layer_types = ["unwrapped_phase", "interferometric_correlation", "temporal_coherence"]

def get_timeseries_at_pixel(
        x: float = 0, 
        y: float = 0, 
        file_stack: list = []
    ) -> list[float]:
    
    # TODO: Make this a numpy structured array
    _read_partial_pixels_at_layers = partial(_read_layers_at_pixel, x=x, y=y)
    values = open_datasets(file_names=file_stack, preprocess=_read_partial_pixels_at_layers)
    # values = [_read_layers_at_pixel(open_dataset(file), x, y) for file in file_stack]

    averages = {layer: _calculate_layer_average(values, layer) for layer in layer_types}
    
    return {layer: value['data'] for layer, value in values.to_dict()['coords'].items()}, averages


# https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset
# pass to pre-process
def _read_layers_at_pixel(dataset: xr.Dataset, x: float, y: float) -> list[xr.DataArray]:
    # reprojects lon lat to dataset projection, returns dict with reading at each layer
    crs = get_crs(dataset)
    xx, yy = _to_crs(x, y, target_proj=crs.to_epsg())
    coordinates = xr.Coordinates({
        layer: [_sample_nearest_pixel(dataset[layer], xx, yy)] for layer in layer_types
        })
    output = xr.DataArray(coords=coordinates)
    return output
def _sample_nearest_pixel(data_layer: xr.DataArray, x: float, y: float) -> Optional[float]:
    # samples nearest pixel to projected x,y value, returns value or None
    try:
        value = data_layer.sel(x=x, y=y, method="nearest", drop=False)
    #     if value.isnull():
    #         value = None
    except KeyError as exc:
        logging.warning(exc)
        value = None
    return value

def _calculate_layer_average(values: dict[str, float | None], layer: str):
    # Iterates over list of dicts containing info for each layer, tries and get the average for all non-nan values across the specified layer
    average = np.average([step[layer] for step in values if step[layer] is not None]).item()
    if math.isnan(average):
        average = None
    return average


def _to_crs(x, y, source_proj='4326', target_proj='32610'): # EPSG:3857 (formerly 32610)
    source_crs = CRS.from_epsg(source_proj)
    target_crs = CRS.from_epsg(target_proj)

    source_to_target = Transformer.from_crs(source_crs, target_crs)
    return source_to_target.transform(x, y)
