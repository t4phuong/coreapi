# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.t4_coreapi.utils.decorators import validate_core_api
from odoo.addons.t4_coreapi.utils.logging import log_core_api

_logger = logging.getLogger(__name__)


class CoreApiController(http.Controller):
    """Base controller — inherit when adding secured Core API endpoints."""

    def _get_device(self):
        device_id = request.env.context.get('core_api_device_id')
        if not device_id:
            return request.env['core.api.device']
        return request.env['core.api.device'].sudo().browse(device_id)


class CoreApiDemoController(CoreApiController):
    """Sample protected endpoints demonstrating gatekeeper + permissions."""

    @http.route(
        '/api/v1/health',
        type='http',
        auth='core_api',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    @validate_core_api('health')
    @log_core_api('api')
    def health(self, **kw):
        device = self._get_device()
        body = {
            'status': 'ok',
            'device': device.name,
            'client_id': device.client_id,
            'message': 'Core API is reachable',
        }
        return request.make_response(
            json.dumps(body),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(
        '/api/v1/orders',
        type='http',
        auth='core_api',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    @validate_core_api('orders')
    @log_core_api('api')
    def list_orders(self, **kw):
        device = self._get_device()
        body = {
            'status': 'ok',
            'device': device.name,
            'orders': [],
            'message': 'Order API placeholder — extend in your module.',
        }
        return request.make_response(
            json.dumps(body),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(
        '/api/v1/hr/employees',
        type='http',
        auth='core_api',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    @validate_core_api('hr')
    @log_core_api('api')
    def list_employees(self, **kw):
        device = self._get_device()
        body = {
            'status': 'ok',
            'device': device.name,
            'employees': [],
            'message': 'HR API placeholder — extend in your module.',
        }
        return request.make_response(
            json.dumps(body),
            headers=[('Content-Type', 'application/json')],
        )
