from fastapi import APIRouter, HTTPException
from app.services.runpod_service import list_pods

router = APIRouter(
    prefix="/api/runpod",
    tags=["runpod"],
)


@router.get("/test")
async def test_runpod():
    try:
        pods = await list_pods()

        return {
            "success": True,
            "message": "RunPod connection successful",
            "pods": pods,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )