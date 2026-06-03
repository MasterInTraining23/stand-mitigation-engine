from typing import Optional
from datetime import datetime
from pydantic import BaseModel, model_validator


class EvaluateRequest(BaseModel):
    observations: dict
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must be before to_date")
        return self
