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
    """Chuẩn hóa dữ liệu đầu vào dựa trên loại request (http hoặc json)."""
    data_body = {}
    
    # 1. Giải mã chuỗi bytes từ body (nếu có)
    if body:
        try:
            body_str = body.decode('utf-8') if isinstance(body, bytes) else body
            data_body = json.loads(body_str) if body_str else {}
        except (json.JSONDecodeError, AttributeError):
            # Nếu không parse được JSON, giữ nguyên dạng raw để tránh sập hệ thống
            data_body = {"raw": body}

    # 2. Xử lý đóng gói ngữ cảnh (Context)
    if ctype == 'json':
        return {
            _CONTEXT_NAME: {
                "params": kw or {},
                # Với request JSON, ưu tiên lấy data_body đã parse, 
                # nếu body trống thì fallback về dữ liệu kw (Odoo tự parse trong một số cấu hình)
                "body": data_body or kw or {},
                "is_json": True
            }
        }
    
    elif ctype == 'http':
        return {
            _CONTEXT_NAME: {
                "params": kw or {},
                "body": data_body,  # Thường là trống hoặc chuỗi thô nếu là HTTP Form
                "is_json": False
            }
        }
    
    return {}

def _extract_context(obj=None):
    """Hàm nội bộ để bóc tách context từ obj (có thể là self, env, hoặc request)."""
    # Trường hợp 1: Không truyền gì, thử lấy từ odoo request toàn cục
    if obj is None:
        return request.env.context if (request and request.env) else {}

    # Trường hợp 2: Đối tượng truyền vào là 'env' của Odoo
    if hasattr(obj, 'context'):
        return obj.context

    # Trường hợp 3: Đối tượng truyền vào là 'self' (Model)
    if hasattr(obj, 'env') and hasattr(obj.env, 'context'):
        return obj.env.context

    # Trường hợp 4: Đối tượng truyền vào trực tiếp là một bản dịch dict context
    if isinstance(obj, dict):
        return obj

    return {}


def get_params(obj=None):
    """Lấy tham số URL/Form (params) đã chuẩn hóa từ trong context ra.

    :param obj: Có thể là self, env, context (dict), hoặc để None (tự nhận diện
    request)
    """
    ctx = _extract_context(obj)
    api_ctx = ctx.get(_CONTEXT_NAME, {})
    return api_ctx.get('params', {})


def get_body(obj=None):
    """Lấy nội dung HTTP Body (JSON/Raw) đã chuẩn hóa từ trong context ra.

    :param obj: Có thể là self, env, context (dict), hoặc để None (tự nhận diện
    request)
    """
    ctx = _extract_context(obj)
    api_ctx = ctx.get(_CONTEXT_NAME, {})
    return api_ctx.get('body', {})