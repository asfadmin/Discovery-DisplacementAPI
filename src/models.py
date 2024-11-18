from typing import Optional
from pydantic import BaseModel, Field


class FsspecParams(BaseModel):
    default_cache_type: Optional[str] = 'blockcache'
    default_block_size: Optional[int] = 64 * 1024 * 1024  # could be bigger


class TimeSeriesModel(BaseModel):
    wkt: str
    file_store: str = Field(pattern=r'^s3://([^/]+)/(.*?([^/]+))$')
    target_files: list[str] = []  # the files to filter from the zarr store before the final result
    fsspec_params: Optional[FsspecParams] = FsspecParams()  # used when opening s3 files by s3fs


class WKTModel(BaseModel):
    wkt: str
