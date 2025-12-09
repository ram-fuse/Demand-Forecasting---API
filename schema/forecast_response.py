from pydantic import BaseModel
from typing import List

class ForecastResponse(BaseModel):
    sku_id: str
    date: List[str]
    demand: List[float]
