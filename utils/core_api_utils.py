from odoo import api
import json
import logging
from functools import wraps
from odoo.http import request

from odoo.addons.t4_coreapi.utils.exception import ensure_dict, CoreApiInvalidBody

_logger = logging.getLogger(__name__)


def endpoint(name=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if not isinstance(result, dict):
                set_response(data=result)
            else:
                message = result.get('message')
                data = result.get('data')
                if not message and not data:
                    set_response(data=result)
                else:
                    set_response(data=data, message=message)
            return result

        wrapper._is_endpoint = True
        wrapper._endpoint_name = name or func.__name__.replace('_', ' ').title()
        return api.model(wrapper)

    return decorator


def route(route=None, name=None):
    def decorator(func):
        func._is_route = True
        func._route = route
        func._endpoint_name = name or func.__name__.replace('_', ' ').title()
        return api.model(func)
    return decorator


# def get_context(kw, body, ctype='http'):
#     """Build the core_api context dict injected into the Odoo environment."""
#     data_body = {}

#     if body:
#         try:
#             body_str = body.decode('utf-8') if isinstance(body, bytes) else body
#             data_body = json.loads(body_str) if body_str else {}
#         except (json.JSONDecodeError, AttributeError):
#             data_body = {"raw": body}

#     if ctype == 'json':
#         return {
#             _CONTEXT_NAME: {
#                 "params": kw or {},
#                 "body": data_body or kw or {},
#                 "is_json": True,
#             }
#         }

#     if ctype == 'http':
#         return {
#             _CONTEXT_NAME: {
#                 "params": kw or {},
#                 "body": data_body,
#                 "is_json": False,
#             }
#         }

#     return {}


def _extract_context(obj=None):
    """Resolve an Odoo context dict from self, env, request, or a raw dict."""
    if hasattr(obj, 'context'):
        return obj.context

    if hasattr(obj, 'env') and hasattr(obj.env, 'context'):
        return obj.env.context

    if isinstance(obj, dict):
        return obj

    return {}


def get_params(obj=None):
    """Return URL or form parameters from the core_api context or request."""
    if not obj:
        return dict(request.httprequest.args) if request else {}

    ctx = _extract_context(obj)
    return ctx.get('core_api_params', {})
   


def get_body(obj=None):
    """Return the parsed JSON body from the core_api context or request."""
    if not obj:
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

    ctx = _extract_context(obj)
    if ctx:
        body = ctx.get('core_api_body')
        if body is None:
            return {}
        return ensure_dict(body)

    return {}


def set_response(data=False, message=False, status_code=200):
    """Build a standard JSON API response via set_api_response."""
    data_field = {"data": data} if data else {}

    response_payload = {
        "status_code": status_code,
        "status": "success" if 200 <= status_code < 300 else "error",
        "message": message if message else "Successful!",
        **data_field,
    }

    request.env["core.api.application"].set_api_response(response_payload)
