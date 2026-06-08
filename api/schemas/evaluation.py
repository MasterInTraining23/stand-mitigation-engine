from typing import Optional
from pydantic import BaseModel, model_validator


class EvaluateRequest(BaseModel):
    observations: dict
    from_date: Optional[int] = None  # epoch milliseconds
    to_date: Optional[int] = None    # epoch milliseconds

    @model_validator(mode="after")
    def validate_range(self):
        if self.from_date is not None and self.to_date is not None:
            if self.from_date > self.to_date:
                raise ValueError("from_date must be before to_date")
        return self
