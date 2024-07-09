from functools import partial
# import rasterio
from src.HDF.data_reader import open_datasets, get_crs
from pyproj import CRS, Transformer
import xarray as xr

from src.models import DriverKeywords, FsspecParams

layer_types = ["unwrapped_phase", "interferometric_correlation", "temporal_coherence"]

def get_timeseries_at_pixel(
        x: float, 
        y: float, 
        file_stack: list[str],
        fsspec_params: FsspecParams,
        driver_config: DriverKeywords
    ) -> tuple[str, dict]:
    
    _read_partial_pixels_at_layers = partial(_read_layers_at_pixel, x=x, y=y)
    values = open_datasets(
        file_names=file_stack, 
        preprocess=_read_partial_pixels_at_layers,
        fsspec_params=fsspec_params, 
        driver_params=driver_config
    )

    averages = values.mean(dim='time', skipna=True)
    averages = {
        'unwrapped_phase': averages['unwrapped_phase'].values.item(),
        'interferometric_correlation': averages['interferometric_correlation'].values.item(),
        'temporal_coherence': averages['temporal_coherence'].values.item()
    }

    return values.to_dataframe().to_json(), averages

# https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset
# pass to pre-process
def _read_layers_at_pixel(dataset: xr.Dataset, x: float, y: float) -> xr.Dataset:
    # reprojects lon lat to dataset projection, returns dict with reading at each layer
    crs = get_crs(dataset)
    xx, yy = _to_crs(x, y, target_proj=crs.to_epsg())
    return dataset[["unwrapped_phase", "interferometric_correlation", "temporal_coherence"]].sel(x=xx, y=yy, method="nearest", drop=True)


def _to_crs(x, y, source_proj='4326', target_proj='32610'): # EPSG:3857 (formerly 32610)
    source_crs = CRS.from_epsg(source_proj)
    target_crs = CRS.from_epsg(target_proj)

    source_to_target = Transformer.from_crs(source_crs, target_crs)
    return source_to_target.transform(x, y)
