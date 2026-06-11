# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import binascii
import datetime
import logging
import os

from passlib.context import CryptContext

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

TOKEN_SIZE = 32
INDEX_SIZE = 8

TOKEN_CRYPT_CONTEXT = CryptContext(['pbkdf2_sha512'], pbkdf2_sha512__rounds=6000)


class CoreApiToken(models.Model):
    _name = 'core.api.token'
    _description = 'Core API Access Token'
    _order = 'create_date desc'

    name = fields.Char(required=True)
    device_id = fields.Many2one(
        'core.api.device',
        required=True,
        ondelete='cascade',
        index=True,
    )
    device_name = fields.Char(related='device_id.name', store=True)
    client_id = fields.Char(related='device_id.client_id', store=True, index=True)
    active = fields.Boolean(default=True)
    expiration_date = fields.Datetime(index=True)
    last_used_at = fields.Datetime(readonly=True)
    last_used_ip = fields.Char(readonly=True)
    token_index = fields.Char(size=INDEX_SIZE, readonly=True, index=True)
    token_hash = fields.Char(readonly=True, groups='base.group_system')

    _index_unique = models.Constraint('unique(token_index)', 'Token index must be unique.')

    @api.model
    def issue_for_device(self, device):
        """Return (plaintext_token, token_record). Revokes previous active tokens."""
        device.ensure_one()
        if device.state != 'active':
            raise UserError(_('Cannot issue a token for an inactive device.'))
        self.sudo().search([
            ('device_id', '=', device.id),
            ('active', '=', True),
        ]).write({'active': False})

        ttl = device.token_ttl_hours
        expiration = (
            False if not ttl
            else fields.Datetime.now() + datetime.timedelta(hours=ttl)
        )
        plaintext = binascii.hexlify(os.urandom(TOKEN_SIZE)).decode()
        token_rec = self.sudo().create({
            'name': f'Token {fields.Datetime.now()}',
            'device_id': device.id,
            'expiration_date': expiration,
            'token_index': plaintext[:INDEX_SIZE],
            'token_hash': TOKEN_CRYPT_CONTEXT.hash(plaintext),
        })
        ip = request.httprequest.environ.get('REMOTE_ADDR', 'n/a') if request else 'n/a'
        _logger.info('Core API token issued for device %s from %s', device.client_id, ip)
        return plaintext, token_rec

    @api.model
    def authenticate(self, plaintext_token):
        """Validate bearer token. Returns (device, token) or (empty, empty)."""
        empty_device = self.env['core.api.device']
        empty_token = self.browse()
        if not plaintext_token or len(plaintext_token) < INDEX_SIZE:
            return empty_device, empty_token
        index = plaintext_token[:INDEX_SIZE]
        tokens = self.sudo().search([
            ('active', '=', True),
            ('token_index', '=', index),
            ('device_id.state', '=', 'active'),
            '|',
            ('expiration_date', '=', False),
            ('expiration_date', '>=', fields.Datetime.now()),
        ])
        for token in tokens:
            if TOKEN_CRYPT_CONTEXT.verify(plaintext_token, token.token_hash):
                ip = request.httprequest.environ.get('REMOTE_ADDR') if request else None
                token.write({'last_used_at': fields.Datetime.now(), 'last_used_ip': ip})
                return token.device_id, token
        return empty_device, empty_token

    def action_revoke(self):
        if not self.env.user.has_group('t4_coreapi.group_core_api_manager'):
            raise AccessError(_('Only Core API managers can revoke tokens.'))
        for token in self:
            token.sudo().write({'active': False})
            _logger.info(
                'Core API token revoked: device %s #%s',
                token.client_id,
                token.id,
            )

    @api.autovacuum
    def _gc_expired_tokens(self):
        expired = self.sudo().search([
            ('active', '=', True),
            ('expiration_date', '!=', False),
            ('expiration_date', '<', fields.Datetime.now()),
        ])
        if expired:
            expired.write({'active': False})
            _logger.info('Core API: deactivated %s expired token(s).', len(expired))
