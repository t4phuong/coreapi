# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID

from odoo.addons.t4_coreapi.hooks import migrate_endpoint_ids_to_server_actions, run_legacy_migrations


def migrate(cr, version):
    run_legacy_migrations(cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    migrate_endpoint_ids_to_server_actions(env)
