# Part of T4 Core API. See LICENSE file for full copyright and licensing details.
from odoo import http
# pyrefly: ignore [missing-import]
from odoo.http import request
# pyrefly: ignore [missing-import]
from odoo.addons.t4_coreapi.utils import CoreApiDispatcher

class CoreApiController(http.Controller):
    """Base controller. Inherit when adding custom secured Core API endpoints."""

    def _dispatcher(self, service_code, version, subpath):
        request.service_info = {
            "service_code": service_code,
            "version": version,
            "subpath": subpath,
            "method": request.httprequest.method,
            "version_code": f"{service_code}/{version}",
            "route_path": f"/{subpath}",
        }

        return CoreApiDispatcher()
