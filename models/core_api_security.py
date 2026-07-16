# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CoreApiRole(models.Model):
    _name = 't4.coreapi.role'
    _description = 'Core API Role'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Role Code', required=True)
    
    service_id = fields.Many2one(
        't4.coreapi.service', 
        string='Service',
        required=True,
        ondelete='cascade')

    _sql_constraints = [
        ('unique_code_per_service', 'UNIQUE(code, service_id)', 'Role code must be unique per service!')
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
