# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

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


def pre_init_hook(cr):
    """Rename legacy core.api.device tables to core.api.application."""
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

    cr.execute("""
        UPDATE ir_model SET model = 'core.api.application'
        WHERE model = 'core.api.device'
    """)
    cr.execute("""
        UPDATE ir_model_fields SET model = 'core.api.application'
        WHERE model = 'core.api.device'
    """)
    cr.execute("""
        UPDATE ir_model_fields
        SET name = 'application_id', field_description = 'Application'
        WHERE model = 'core.api.application' AND name = 'device_id'
    """)
    cr.execute("""
        UPDATE ir_model_fields
        SET name = 'application_name', field_description = 'Application Name'
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


def post_init_hook(env):
    """Ensure sample routes have a Server Action on upgrade."""
    health_action = env.ref('t4_coreapi.action_health_server', raise_if_not_found=False)
    health_endpoint = env.ref('t4_coreapi.endpoint_health', raise_if_not_found=False)
    if health_action and health_endpoint and not health_endpoint.action_id:
        health_endpoint.sudo().write({'action_id': health_action.id})


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
