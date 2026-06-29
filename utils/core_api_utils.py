from odoo import api
import json
import logging
from odoo.http import request

from odoo.addons.t4_coreapi.utils.exception import ensure_dict, CoreApiInvalidBody

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
                "is_json": True,
            }
        }

    if ctype == 'http':
        return {
            _CONTEXT_NAME: {
                "params": kw or {},
                "body": data_body,
                "is_json": False,
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
    """Return URL or form parameters from the core_api context or request."""
    ctx = _extract_context(obj)
    api_ctx = ctx.get(_CONTEXT_NAME)
    if api_ctx:
        return api_ctx.get('params', {})
    if not request:
        return {}
    return request.params or {}


def get_body(obj=None):
    """Return the parsed JSON body from the core_api context or request."""
    ctx = _extract_context(obj)
    api_ctx = ctx.get(_CONTEXT_NAME)
    if api_ctx:
        body = api_ctx.get('body', {})
        return body if body is not None else {}

    if not request:
        return {}

    raw_data = request.httprequest.data
    if not raw_data:
        return {}

    try:
        parsed_data = json.loads(raw_data)
    except Exception:
        raise CoreApiInvalidBody('Request body is not valid JSON.')

    return ensure_dict(parsed_data)


def set_response(data=False, message='Request processed successfully.', status_code=200):
    """Build a standard JSON API response via set_api_response."""
    from odoo.addons.t4_coreapi.utils.response import STATUS_ERROR, STATUS_SUCCESS

    response_payload = {
        'status_code': status_code,
        'status': STATUS_SUCCESS if 200 <= status_code < 300 else STATUS_ERROR,
        'message': message,
    }
    if data is not False and data is not None:
        response_payload['data'] = data

    request.env['core.api.application'].set_api_response(response_payload)
