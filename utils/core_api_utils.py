from odoo import api
import json
import logging
from odoo.http import request


_logger = logging.getLogger(__name__)

_CONTEXT_NAME = "core_api"


def endpoint(name=None):
    def decorator(func):
        func._is_endpoint = True
        func._endpoint_name = name or func.__name__.replace('_', ' ').title()
        return api.model(func)
    return decorator

def route(route=None, name=None):
    def decorator(func):
        func._is_route = True
        func._route = route
        func._endpoint_name = name or func.__name__.replace('_', ' ').title()
        return api.model(func)
    return decorator


def get_context(kw, body, ctype='http'):
    """Build the core_api context dict injected into the Odoo environment."""
    data_body = {}

    if body:
        try:
            body_str = body.decode('utf-8') if isinstance(body, bytes) else body
            data_body = json.loads(body_str) if body_str else {}
        except (json.JSONDecodeError, AttributeError):
            data_body = {"raw": body}

    if ctype == 'json':
        return {
            _CONTEXT_NAME: {
                "params": kw or {},
                "body": data_body or kw or {},
                "is_json": True
            }
        }

    if ctype == 'http':
        return {
            _CONTEXT_NAME: {
                "params": kw or {},
                "body": data_body,
                "is_json": False
            }
        }

    return {}


def _extract_context(obj=None):
    """Resolve an Odoo context dict from self, env, request, or a raw dict."""
    if obj is None:
        return request.env.context if (request and request.env) else {}

    if hasattr(obj, 'context'):
        return obj.context

    if hasattr(obj, 'env') and hasattr(obj.env, 'context'):
        return obj.env.context

    if isinstance(obj, dict):
        return obj

    return {}


def get_params(obj=None):
    """Return URL or form parameters from the normalized core_api context."""
    ctx = _extract_context(obj)
    api_ctx = ctx.get(_CONTEXT_NAME, {})
    return api_ctx.get('params', {})


def get_body(obj=None):
    """Return the parsed JSON body from the normalized core_api context."""
    ctx = _extract_context(obj)
    api_ctx = ctx.get(_CONTEXT_NAME, {})
    body = api_ctx.get('body', {})
    if body is None:
        body = {}
    return body
