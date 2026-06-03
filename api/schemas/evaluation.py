from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class EvaluateRequest(BaseModel):
    observations: dict
    as_of: Optional[datetime] = None
