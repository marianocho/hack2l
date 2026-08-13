"""Invariante de convencao (docs/REFERENCE_GUIDE.md:71):

    "Every endpoint returns a Pydantic schema from `schemas.py`."

Todo endpoint de API que devolve corpo tem que declarar response_model, e esse
response_model tem que ser um tipo (ou list de tipo) definido em app.schemas.
Isso vale no commit base; o teste falha se algum endpoint novo devolver dict cru.
"""
import inspect

import pytest
from fastapi.routing import APIRoute

from app import schemas
from app.main import app

EXCLUDED_PATHS = {"/health"}

SCHEMA_TYPES = {
    obj
    for _, obj in inspect.getmembers(schemas, inspect.isclass)
}


def _body_routes():
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in EXCLUDED_PATHS:
            continue
        if route.status_code == 204:
            continue
        methods = route.methods - {"HEAD", "OPTIONS"}
        if not methods:
            continue
        yield route


def _declares_schema(model) -> bool:
    if model is None:
        return False
    if model in SCHEMA_TYPES:
        return True
    args = getattr(model, "__args__", ())
    return bool(args) and all(a in SCHEMA_TYPES for a in args)


def test_every_endpoint_returns_a_pydantic_schema():
    offenders = [
        f"{sorted(r.methods)} {r.path} -> response_model={r.response_model!r}"
        for r in _body_routes()
        if not _declares_schema(r.response_model)
    ]
    assert offenders == [], (
        "endpoints devolvendo corpo sem schema Pydantic de app/schemas.py: "
        + "; ".join(offenders)
    )
