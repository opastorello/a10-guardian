from pydantic import BaseModel


class GenericResponse(BaseModel):
    message: str | None = None
    status: str | None = None
