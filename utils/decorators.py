# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import functools
import logging

from werkzeug.exceptions import Forbidden

from odoo.http import request

_logger = logging.getLogger(__name__)


def validate_core_api(endpoint_code=None, check_route=False):
    """Decorator for Core API controllers — enforces per-application API permissions.

    Usage::

        @http.route('/api/v1/orders', auth='core_api', ...)
        @validate_core_api('orders')
        def list_orders(self, **kw):
            ...

    If ``endpoint_code`` is omitted, the allowed endpoint catalog is matched
    against the current request path (same as ``check_route=True``).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            application_id = request.env.context.get('core_api_application_id')
            if not application_id:
                raise Forbidden('Core API application context missing — use auth="core_api".')
            application = request.env['core.api.application'].sudo().browse(application_id)
            if not application:
                raise Forbidden('Unknown Core API application.')
            if endpoint_code:
                application.check_api_access_by_code(endpoint_code)
            else:
                application.check_route_access(request.httprequest.path)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
