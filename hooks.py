# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

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
