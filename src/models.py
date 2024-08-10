from typing import Annotated, Optional
from pydantic import BaseModel, UrlConstraints
from pydantic_core import Url


class DriverKeywords(BaseModel):
    page_buf_size: Optional[int] = 32 * 1024 * 1024  # this one only works in repacked files
    rdcc_nbytes: Optional[int] = 24 * 1024 * 1024  # this one is to read the chunks
    rdcc_nslots: Optional[int] = 641  # default is 521, prime numbers recommended


class FsspecParams(BaseModel):
    cache_type: Optional[str] = (
        'first'  # blockcache not working atm for some reason with open_mfdataset, using first
    )
    block_size: Optional[int] = 24 * 1024 * 1024  # could be bigger


class TimeSeriesModel(BaseModel):
    # files: list[str]
    file_store: str
    lon: float = 0.0
    lat: float = 0.0

    # for open_mfdataset and fsspec, are key points of optimization
    driver_kwds: Optional[DriverKeywords] = (
        DriverKeywords()
    )  # passed along to the engine open_mfdataset uses (h5netcdf)
    fsspec_params: Optional[FsspecParams] = FsspecParams()  # used when opening s3 files by s3fs


class KerchunkFileModel(BaseModel):
    file_uri: Annotated[Url, UrlConstraints(allowed_schemes=['s3'])]
    destination: Annotated[Url, UrlConstraints(allowed_schemes=['s3'])] # = Field(pattern=r'(s3:\/\/)(\S|\/)*\/')
    destination_filename: Optional[
        str
    ] = None


class KerchunkStackModel(BaseModel):
    files: list[str]
    destination_bucket: str

class WKTModel(BaseModel):
    wkt: str