from fastapi import APIRouter, Path, Request
from typing import Annotated
from app.services.brasil_api import check_rate_limit, lookup_cep

router = APIRouter(prefix="/brasil", tags=["BrasilAPI"])


@router.get("/cep/{cep}")
def cep_lookup(cep: Annotated[str, Path(pattern=r"^\d{8}$")], request: Request):
    check_rate_limit(request, "cep")
    return lookup_cep(cep)
