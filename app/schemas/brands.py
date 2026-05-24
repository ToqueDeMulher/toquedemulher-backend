from pydantic import BaseModel

class BrandRequest(BaseModel):
    name: str