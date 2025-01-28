from typing import Literal
from pydantic import BaseModel, Field, field_validator
from .constants import Polarizations

class GetFramesModel(BaseModel):
    wkt: str
    flightDirection: str = Field(pattern=r'((ASC)|(DESC))(ENDING)?', default='ASC')

    @field_validator('flightDirection', mode='before')
    @classmethod
    def pre_validate_flightdir(cls, v: str) -> str:
        return v.upper()

    @field_validator('flightDirection', mode='after')
    @classmethod
    def post_validate_flightdir(cls, v: str) -> str:
        return 'ASCENDING' if v in 'ASCENDING' else 'DESCENDING'

class TimeSeriesModel(GetFramesModel):
    bucket: str = Field(pattern=r'[^/^\\]*')
    polarization: Polarizations = Polarizations.VV
