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
    coreapi_data = get_coreapi_data(env)
    if 'body' in coreapi_data and coreapi_data['body']:
        try:
            return json.loads(coreapi_data['body'])
        except Exception:
            return {}
    if request and request.httprequest.data:
        try:
            return json.loads(request.httprequest.data)
        except Exception:
            return {}
    return {}

def get_params(env=None):
    coreapi_data = get_coreapi_data(env)
    if 'params' in coreapi_data:
        return coreapi_data['params']
    if request:
        return request.params
    return {}

def get_headers(env=None):
    coreapi_data = get_coreapi_data(env)
    if 'header' in coreapi_data:
        return coreapi_data['header']
    return {}

def get_state(env=None):
    coreapi_data = get_coreapi_data(env)
    if 'state' in coreapi_data:
        return coreapi_data['state']
    return {}

def get_route(env=None):
    coreapi_data = get_coreapi_data(env)
    if 'route' in coreapi_data:
        return coreapi_data['route']
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
