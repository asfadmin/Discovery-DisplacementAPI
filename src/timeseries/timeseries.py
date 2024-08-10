

# import rasterio
from src.HDF.data_reader import open_zarr_store, get_crs
from pyproj import CRS, Transformer
import xarray as xr
from src.models import DriverKeywords, FsspecParams
# from pandas import DataFrame

layer_types = ['unwrapped_phase', 'interferometric_correlation', 'temporal_coherence']

_data_variables = [
    *layer_types,
    'time',
]


def get_timeseries_at_pixel(
    lat: float,
    lon: float,
    file_store: str,
    fsspec_params: FsspecParams,
    driver_config: DriverKeywords,
) -> str:
    values = open_zarr_store(
        file_store=file_store,
        fsspec_params=fsspec_params,
        driver_params=driver_config,
    )
    values = _read_layers_at_pixel(values, lat, lon)

    # meta = DataFrame(file_meta, columns=['fileName', 'bytes'])
    pandas_values = values.to_pandas()
    # pandas_values = pandas_values.assign(
    #     fileName=meta['fileName'].values, bytes=meta['bytes'].values
    # )

    # sort by time, make fileName column the index for our data for nicer json output
    # pandas_values = pandas_values.sort_index().reset_index().set_index('fileName')
    pandas_values.loc['mean'] = pandas_values.mean(skipna=True, numeric_only=True)
    pandas_json = pandas_values.to_json(date_format='iso', orient='index')
    return pandas_json


# https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset
# pass to pre-process
def _read_layers_at_pixel(dataset: xr.Dataset, lat: float, lon: float) -> xr.Dataset:
    # reprojects lon lat to dataset projection, returns dict with reading at each layer
    crs = get_crs(dataset)
    xx, yy = _to_crs(lat, lon, target_proj=crs.to_epsg())
    return dataset[_data_variables].sel(x=xx, y=yy, method='nearest', drop=True)


def _to_crs(lat: float, lon: float, source_proj='4326', target_proj='32610'):
    source_crs = CRS.from_epsg(source_proj)
    target_crs = CRS.from_epsg(target_proj)

    source_to_target = Transformer.from_crs(source_crs, target_crs)
    return source_to_target.transform(lat, lon)
