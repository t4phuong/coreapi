from odoo import api
import json
import logging
from odoo.http import request

from odoo.addons.t4_coreapi.utils.exception import ensure_dict, CoreApiInvalidBody


_logger = logging.getLogger(__name__)

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


def get_params():
    """
    Lấy các tham số (query string) từ URL.
    Trả về một dictionary.
    """
    if not request:
        return {}
    return request.params or {}

def get_body():
    """
    Lấy và chuyển đổi dữ liệu body từ dạng JSON raw sang Dictionary.
    Có xử lý lỗi để tránh sập (crash) API và đảm bảo payload luôn là dict.
    """
    if not request:
        return {}
    
    raw_data = request.httprequest.data
    if not raw_data:
        return {}
        
    try:
        parsed_data = json.loads(raw_data)
    except Exception:
        # Thay vì trả về {}, ta báo lỗi định dạng JSON không hợp lệ
        raise CoreApiInvalidBody('Request body is not valid JSON.')
        
    # Chạy qua hàm kiểm tra để chặn các trường hợp gửi lên List [] hoặc String
    return ensure_dict(parsed_data)

def set_response(data=False, message="Thao tác thành công", status_code=200):
    """
    Đóng gói kết quả trả về. 
    Người dùng chỉ cần truyền env, message và data. Các trường khác tự động được tạo.
    """
    data_field = {"data": data} if data else {}

    response_payload = {
        "status_code": status_code,
        "status": "success" if 200 <= status_code < 300 else "error",
        "message": message,
        **data_field
    }
    
    request.env["core.api.application"].set_api_response(response_payload)