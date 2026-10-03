from fastapi import APIRouter, HTTPException

from backend.models.schemas import PredictionRequest, PredictionResponse
from backend.services.prediction_service import prediction_service


router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.post("", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    try:
        return prediction_service.predict(request)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
