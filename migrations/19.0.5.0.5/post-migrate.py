# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from odoo.addons.t4_coreapi.hooks import _table_exists


def migrate(cr, version):
    """Restore endpoint_ids from server_action_ids (19.0.5.0.2–19.0.5.0.4)."""
    if not _table_exists(cr, 'core_api_application_server_action_rel'):
        return
    if not _table_exists(cr, 'core_api_application_endpoint_rel'):
        return
    cr.execute("""
        INSERT INTO core_api_application_endpoint_rel (application_id, endpoint_id)
        SELECT DISTINCT sa.application_id, e.id
        FROM core_api_application_server_action_rel sa
        JOIN core_api_endpoint e ON e.action_id = sa.server_action_id
        ON CONFLICT DO NOTHING
    """)
