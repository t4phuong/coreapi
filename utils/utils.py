# pyrefly: ignore [missing-import]
import json
import functools
from odoo import api
# pyrefly: ignore [missing-import]
from odoo.http import request
from .dispatcher import CoreApiDispatcher

def get_coreapi_data(env=None):
    if env:
        return env.context.get('core api', {})
    return {}

def get_body(env=None):
    if env and 'body' in env.context and env.context['body']:
        try:
            return json.loads(env.context['body'])
        except Exception:
            return {}
    if request and request.httprequest.data:
        try:
            return json.loads(request.httprequest.data)
        except Exception:
            return {}
    return {}

def get_params(env=None):
    if env and 'params' in env.context and env.context['params']:
        return env.context['params']
    if request:
        return request.params
    return {}

def get_headers(env=None):
    if env and 'header' in env.context and env.context['header']:
        return env.context['header']
    return {}

def get_state(env=None):
    if env and 'state' in env.context and env.context['state']:
        return env.context['state']
    return {}

def get_route(env=None):
    if env and 'route' in env.context and env.context['route']:
        return env.context['route']
    if request:
        return getattr(request, 'coreapi_route', None)
    return None

def endpoint(name):
    def decorator(func):
        @api.model
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            status_code = 200
            if isinstance(result, tuple) and len(result) == 2:
                data, status_code = result
            else:
                data = result
            
            # Auto-set response
            if data is not None:
                CoreApiDispatcher.set_response(data, status_code)
                
            return result
            
        wrapper._is_endpoint = True
        wrapper._endpoint_name = name
        return wrapper
    return decorator
