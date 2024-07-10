from typing import Optional
from pydantic import BaseModel, ConfigDict

class DriverKeywords(BaseModel):
    page_buf_size: Optional[int] = 32*1024*1024 # this one only works in repacked files
    rdcc_nbytes: Optional[int] = 24*1024*1024 # this one is to read the chunks 
    rdcc_nslots: Optional[int] = 641 #2 #997 # default is 521
    
    model_config = ConfigDict(extra='forbid')

class FsspecParams(BaseModel):
    cache_type: Optional[str] = "first"  # blockcache not working atm for some reason with open_mfdataset, using first
    block_size: Optional[int] = 24*1024*1024  #24*1024*1024, # could be bigger
    
    model_config = ConfigDict(extra='forbid')

class TimeSeriesModel(BaseModel):
    files: list[str]
    lon: float = 0.0
    lat: float = 0.0
    
    # for open_mfdataset and fsspec, are key points of optimization
    driver_kwds: Optional[DriverKeywords] = DriverKeywords() # passed along to the engine open_mfdataset uses (h5netcdf)
    fsspec_params: Optional[FsspecParams] = FsspecParams() # used when opening s3 files by s3fs

    model_config = ConfigDict(extra='forbid')
