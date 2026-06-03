from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from api.schemas.evaluation import EvaluateRequest
from engine.evaluator import evaluate_property

router = APIRouter()


@router.post("/evaluate")
def evaluate(request: EvaluateRequest, db: Session = Depends(get_db)):
    return evaluate_property(
        request.observations,
        db,
        from_date=request.from_date,
        to_date=request.to_date,
    )
