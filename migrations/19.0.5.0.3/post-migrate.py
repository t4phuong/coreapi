# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from odoo.addons.t4_coreapi.hooks import run_legacy_migrations


def migrate(cr, version):
    run_legacy_migrations(cr)
