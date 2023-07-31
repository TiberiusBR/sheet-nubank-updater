from pydantic import BaseModel


class DefaultResponse(BaseModel):
    description: str
    value: str
    category: str
