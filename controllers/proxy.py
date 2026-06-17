# Part of T4 Core API. See LICENSE file for full copyright and licensing details.
import logging, json
from odoo import http
from odoo.http import request
from odoo.addons.t4_coreapi.controllers.base import CoreApiController
from odoo.addons.t4_coreapi.utils import (
    log_core_api,
    get_context,
)
_logger = logging.getLogger(__name__)

class CoreApiProxyController(CoreApiController):
    """API gateway — applications call Odoo routes; Odoo validates then runs Server Actions."""
    @http.route(
        [
            '/api/v1/<path:subpath>',
        ],
        type='http',
        auth='core_api',
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        csrf=False,
        save_session=False,
    )
    @log_core_api('api')
    def gateway(self, subpath, **kw):
        path = f'/api/v1/{subpath}'
        application = self._get_application()

        ctx = get_context(
            kw, 
            request.httprequest.get_data()
        )

        return request.env['core.api.endpoint'].with_context(
            **ctx
        ).dispatch_request(path, application)

