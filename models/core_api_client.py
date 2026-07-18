# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid

# pyrefly: ignore [missing-import]
from werkzeug.security import generate_password_hash, check_password_hash

class CoreApiClient(models.Model):
    _name = 't4.coreapi.client'
    _description = 'Core API Client'

    name = fields.Char(string='Client Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    username = fields.Char(string='Username', required=True)
    password = fields.Char(string='Password', required=True, help="Will be hashed on save")

    role_ids = fields.Many2many(
        't4.coreapi.role',
        string='API Roles')

    service_id = fields.Many2one(
        't4.coreapi.service',
        string='Service',
        required=True,
        ondelete='cascade')

    _unique_client_per_service = models.Constraint(
        "UNIQUE(username, service_id)",
        "Username must be unique per service!"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'password' in vals and vals['password']:
                vals['password'] = generate_password_hash(vals['password'])
        return super().create(vals_list)

    def write(self, vals):
        if 'password' in vals and vals['password']:
            if not vals['password'].startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
                vals['password'] = generate_password_hash(vals['password'])
        return super().write(vals)

    def read(self, fields=None, load='_classic_read'):
        res = super().read(fields=fields, load=load)
        for record_dict in res:
            if 'password' in record_dict:
                record_dict['password'] = False
        return res

    def check_password(self, password):
        self.ensure_one()
        if not self.password or not password:
            return False
        try:
            return check_password_hash(self.password, password)
        except ValueError:
            return self.password == password
