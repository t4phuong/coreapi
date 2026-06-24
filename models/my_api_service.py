# -*- coding: utf-8 -*-
from odoo import models

from odoo.addons.t4_coreapi.utils import endpoint, set_response, get_body, get_params


class MyApiService(models.Model):
    _inherit = 'res.partner'

    @endpoint('ping')
    def api_ping(self):
        return set_response(data="Hello World")