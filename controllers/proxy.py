# Part of T4 Core API. See LICENSE file for full copyright and licensing details.
import logging
_logger = logging.getLogger(__name__)
from odoo import http
# pyrefly: ignore [missing-import]
from odoo.addons.t4_coreapi.controllers.base import CoreApiController



class CoreApiProxyController(CoreApiController):
    """HTTP gateway: validate token, then run the matching server action."""

    @http.route(
        '/<string:service_code>/<string:version>/<path:subpath>',
        type='http',
        auth='public',
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        csrf=False,
        save_session=False,
    )
    # @log_core_api('api')
    def gateway(self, service_code, version, subpath, **kw):
        """Handle gateway routes: /{service_code}/{version}/{route_suffix}."""
        dispatcher = self._dispatcher(service_code, version, subpath)

        return dispatcher.dispatch()