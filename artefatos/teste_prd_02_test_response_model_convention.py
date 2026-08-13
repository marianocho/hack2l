"""Invariante: todo endpoint que devolve corpo declara um response_model
Pydantic de app.schemas (docs/REFERENCE_GUIDE.md:71). Endpoints 204 sem corpo
e /health estao fora.

Vale no commit base; deve falhar se um router novo devolver dicts crus.
"""
import inspect

from fastapi.routing import APIRoute
from pydantic import BaseModel

from app import schemas
from app.main import app

EXEMPT_PATHS = {"/health", "/", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}

SCHEMA_CLASSES = {
    obj
    for _, obj in inspect.getmembers(schemas, inspect.isclass)
    if issubclass(obj, BaseModel)
}


def _declared(route):
    model = route.response_model
    if model is None:
        return None
    args = getattr(model, "__args__", None)
    if args:
        return args[0]
    return model


def test_every_body_returning_endpoint_uses_a_pydantic_schema():
    offenders = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in EXEMPT_PATHS:
            continue
        if route.status_code == 204:  # sem corpo, nao precisa de schema
            continue
        model = _declared(route)
        if model is None or model not in SCHEMA_CLASSES:
            offenders.append(f"{sorted(route.methods)} {route.path} -> {model!r}")
    assert offenders == [], (
        "endpoints sem response_model Pydantic de schemas.py: " + "; ".join(offenders)
    )
