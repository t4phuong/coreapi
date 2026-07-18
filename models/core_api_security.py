# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CoreApiRole(models.Model):
    _name = 't4.coreapi.role'
    _description = 'Core API Role'

    name = fields.Char(string='Name', required=True)
    
    service_id = fields.Many2one(
        't4.coreapi.service', 
        string='Service',
        required=True,
        ondelete='cascade')

    implied_ids = fields.Many2many(
        't4.coreapi.role',
        't4_coreapi_role_implied_rel',
        'role_id',
        'implied_id',
        string='Implies',
        help="Roles automatically granted to users with this role."
    )

    _sql_constraints = [
        ('unique_name_per_service', 'UNIQUE(name, service_id)', 'Role name must be unique per service!')
    ]

class CoreApiRateLimitLog(models.Model):
    _name = 't4.coreapi.rate.limit.log'
    _description = 'Core API Rate Limit Log'
    _log_access = False # Optimize performance, don't need create_uid, write_uid...

    service_id = fields.Many2one(
        't4.coreapi.service', 
        string='Service',
        required=True,
        ondelete='cascade',
        index=True)

    client_id = fields.Many2one(
        't4.coreapi.client',
        string='Client',
        ondelete='cascade',
        index=True)
        
    session_id = fields.Many2one(
        't4.coreapi.auth.session',
        string='Session',
        ondelete='cascade',
        index=True)
    
    create_date = fields.Datetime(
        string='Created on', 
        default=fields.Datetime.now,
        index=True)

    @api.model
    def action_clean_rate_limit_logs(self):
        """
        Garbage Collector: Deletes logs older than 6 hours.
        The rate limiting now uses a sliding window (create_date >= time_limit),
        so we only need to clean up old data to prevent database bloat.
        """
        self.env.cr.execute("DELETE FROM t4_coreapi_rate_limit_log WHERE create_date < NOW() - INTERVAL '6 hours'")
