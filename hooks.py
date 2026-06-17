# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

_IR_MODEL_DATA_RENAMES = [
    ('model_core_api_device', 'model_core_api_application'),
    ('model_core_api_device_secret_wizard', 'model_core_api_application_secret_wizard'),
    ('access_core_api_device_manager', 'access_core_api_application_manager'),
    ('access_core_api_device_secret_wizard_manager', 'access_core_api_application_secret_wizard_manager'),
    ('action_core_api_device', 'action_core_api_application'),
    ('menu_core_api_devices', 'menu_core_api_applications'),
    ('view_core_api_device_list', 'view_core_api_application_list'),
    ('view_core_api_device_form', 'view_core_api_application_form'),
    ('view_core_api_device_secret_wizard_form', 'view_core_api_application_secret_wizard_form'),
]


def _table_exists(cr, table_name):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table_name,),
    )
    return cr.fetchone()[0]


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s AND column_name = %s
        )
        """,
        (table_name, column_name),
    )
    return cr.fetchone()[0]


def _xmlid_exists(cr, name):
    cr.execute(
        """
        SELECT 1 FROM ir_model_data
        WHERE module = 't4_coreapi' AND name = %s
        LIMIT 1
        """,
        (name,),
    )
    return bool(cr.fetchone())


def _rename_xmlid(cr, old_name, new_name):
    if _xmlid_exists(cr, new_name) or not _xmlid_exists(cr, old_name):
        return
    cr.execute(
        """
        UPDATE ir_model_data
        SET name = %s
        WHERE module = 't4_coreapi' AND name = %s
        """,
        (new_name, old_name),
    )


def _migrate_device_tables(cr):
    if not _table_exists(cr, 'core_api_device'):
        return
    if _table_exists(cr, 'core_api_application'):
        return

    cr.execute('ALTER TABLE core_api_device RENAME TO core_api_application')

    if _table_exists(cr, 'core_api_device_endpoint_rel'):
        cr.execute(
            'ALTER TABLE core_api_device_endpoint_rel '
            'RENAME TO core_api_application_endpoint_rel'
        )
        if _column_exists(cr, 'core_api_application_endpoint_rel', 'device_id'):
            cr.execute(
                'ALTER TABLE core_api_application_endpoint_rel '
                'RENAME COLUMN device_id TO application_id'
            )

    for table in ('core_api_token', 'core_api_log'):
        if _column_exists(cr, table, 'device_id'):
            cr.execute(f'ALTER TABLE {table} RENAME COLUMN device_id TO application_id')


def _migrate_ir_model_metadata(cr):
    """Rename ir.model records only — do not touch field_description (JSON in Odoo 19)."""
    cr.execute("""
        UPDATE ir_model SET model = 'core.api.application'
        WHERE model = 'core.api.device'
    """)
    cr.execute("""
        UPDATE ir_model_fields SET model = 'core.api.application'
        WHERE model = 'core.api.device'
    """)
    cr.execute("""
        UPDATE ir_model_fields SET name = 'application_id'
        WHERE model IN ('core.api.application', 'core.api.token', 'core.api.log')
          AND name = 'device_id'
    """)
    cr.execute("""
        UPDATE ir_model_fields SET name = 'application_name'
        WHERE model = 'core.api.token' AND name = 'device_name'
    """)
    cr.execute("""
        UPDATE ir_model SET model = 'core.api.application.secret.wizard'
        WHERE model = 'core.api.device.secret.wizard'
    """)
    cr.execute("""
        UPDATE ir_model_fields SET model = 'core.api.application.secret.wizard'
        WHERE model = 'core.api.device.secret.wizard'
    """)
    cr.execute("""
        UPDATE ir_model_fields SET name = 'application_id'
        WHERE model = 'core.api.application.secret.wizard' AND name = 'device_id'
    """)


def run_legacy_migrations(cr):
    """Only runs when upgrading from the old device-based module."""
    if not _table_exists(cr, 'core_api_device') and not _xmlid_exists(cr, 'model_core_api_device'):
        return
    _migrate_device_tables(cr)
    _migrate_ir_model_metadata(cr)
    for old_name, new_name in _IR_MODEL_DATA_RENAMES:
        _rename_xmlid(cr, old_name, new_name)


def migrate_endpoint_ids_to_server_actions(env):
    if not _table_exists(env.cr, 'core_api_application_endpoint_rel'):
        return
    if not _table_exists(env.cr, 'core_api_application_server_action_rel'):
        return
    env.cr.execute("""
        SELECT DISTINCT rel.application_id, e.action_id
        FROM core_api_application_endpoint_rel rel
        JOIN core_api_endpoint e ON e.id = rel.endpoint_id
        WHERE e.action_id IS NOT NULL
    """)
    rows = env.cr.fetchall()
    if not rows:
        return
    Application = env['core.api.application'].sudo()
    for app_id, action_id in rows:
        app = Application.browse(app_id)
        if action_id not in app.server_action_ids.ids:
            app.write({'server_action_ids': [(4, action_id)]})


def post_load():
    """Allow ?db= on API routes when multiple databases are installed."""
    import odoo.http

    original = odoo.http.Request._get_session_and_dbname

    def _get_session_and_dbname_with_query_db(self):
        session, dbname = original(self)
        if dbname:
            return session, dbname
        query_db = (self.httprequest.args.get('db') or '').strip()
        host = self.httprequest.environ['HTTP_HOST']
        if query_db and query_db in odoo.http.db_filter([query_db], host=host):
            session.can_save = False
            session.db = query_db
            return session, query_db
        return session, dbname

    odoo.http.Request._get_session_and_dbname = _get_session_and_dbname_with_query_db
