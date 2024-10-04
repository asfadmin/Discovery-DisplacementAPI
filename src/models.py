from typing import Annotated, Optional
from pydantic import BaseModel, Field, UrlConstraints
from pydantic_core import Url


class FsspecParams(BaseModel):
    default_cache_type: Optional[str] = 'blockcache'
    default_block_size: Optional[int] = 24 * 1024 * 1024  # could be bigger


class TimeSeriesModel(BaseModel):
    wkt: str
    file_store: str = Field(pattern=r'^s3://([^/]+)/(.*?([^/]+))$')
    target_files: list[str] = []  # the files to filter from the zarr store before the final result
    fsspec_params: Optional[FsspecParams] = FsspecParams()  # used when opening s3 files by s3fs


class KerchunkFileModel(BaseModel):
    file_uri: str  # Annotated[Url, UrlConstraints(allowed_schemes=['s3'])]
    destination: str  # Annotated[Url, UrlConstraints(allowed_schemes=['s3'])]
    destination_filename: Optional[str] = None


class KerchunkStackModel(BaseModel):
    files: list[str]
    destination_bucket: str


class WKTModel(BaseModel):
    wkt: str
