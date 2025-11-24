"""Info storage routes."""

import json

from fastapi import APIRouter, HTTPException

from ..schemas import InfoRequest, InfoResponse
from ..services.info_store import read_info, write_info

router = APIRouter()


@router.post("/info", response_model=InfoResponse)
async def handle_info(request: InfoRequest) -> InfoResponse:
    if not request.name:
        raise HTTPException(status_code=400, detail="name is required")

    if request.type == "getInfo":
        stored = await read_info(request.name)
        return InfoResponse(code=200, data=stored)

    if request.type == "writeInfo":
        if request.data is None:
            raise HTTPException(status_code=400, detail="data is required for writeInfo")

        if isinstance(request.data, str):
            serialized = request.data
        else:
            try:
                serialized = json.dumps(request.data, ensure_ascii=True)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="data must be JSON serializable") from exc

        await write_info(request.name, serialized)
        return InfoResponse(code=200, data=serialized)

    raise HTTPException(status_code=400, detail="Unsupported request type")
