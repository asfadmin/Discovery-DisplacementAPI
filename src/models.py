from pydantic import BaseModel, Field
from .constants import Polarizations


class WKTModel(BaseModel):
    wkt: str


class TimeSeriesModel(WKTModel):
    bucket: str = Field(pattern=r'[^/^\\]*')
    polarization: Polarizations = Polarizations.VV
