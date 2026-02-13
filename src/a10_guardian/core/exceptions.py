from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


# Template-specific exceptions
class TemplateNotFoundError(Exception):
    """Raised when template file doesn't exist."""

    pass


class TemplateValidationError(Exception):
    """Raised when template fails structural validation (Pydantic or file I/O)."""

    pass


class TemplateA10ValidationError(Exception):
    """Raised when A10 profiles/policies don't exist."""

    pass


async def http_exception_handler(request: Request, exc: HTTPException):
    problem = ProblemDetails(title="HTTP Error", status=exc.status_code, detail=exc.detail, instance=str(request.url))
    return JSONResponse(status_code=exc.status_code, content=problem.model_dump())


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    problem = ProblemDetails(title="Validation Error", status=422, detail=str(exc), instance=str(request.url))
    return JSONResponse(status_code=422, content=problem.model_dump())


async def generic_exception_handler(request: Request, exc: Exception):
    problem = ProblemDetails(
        title="Internal Server Error", status=500, detail="An unexpected error occurred.", instance=str(request.url)
    )
    return JSONResponse(status_code=500, content=problem.model_dump())


async def template_not_found_handler(request: Request, exc: TemplateNotFoundError):
    problem = ProblemDetails(
        type="https://tools.ietf.org/html/rfc7231#section-6.5.4",
        title="Template Not Found",
        status=404,
        detail=str(exc),
        instance=str(request.url),
    )
    return JSONResponse(status_code=404, content=problem.model_dump())


async def template_validation_handler(request: Request, exc: TemplateValidationError):
    problem = ProblemDetails(
        type="https://tools.ietf.org/html/rfc7231#section-6.5.1",
        title="Template Validation Error",
        status=400,
        detail=str(exc),
        instance=str(request.url),
    )
    return JSONResponse(status_code=400, content=problem.model_dump())


async def template_a10_validation_handler(request: Request, exc: TemplateA10ValidationError):
    problem = ProblemDetails(
        type="https://tools.ietf.org/html/rfc7231#section-6.5.1",
        title="A10 Validation Error",
        status=400,
        detail=str(exc),
        instance=str(request.url),
    )
    return JSONResponse(status_code=400, content=problem.model_dump())
