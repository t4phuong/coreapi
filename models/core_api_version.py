# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request

APPLICATION_FORM_VIEW_XML_ID = 't4_coreapi.view_core_api_application_form'

ENDPOINT_VERSION_TAB_LIST_ARCH = """
<list editable="bottom">
    <field name="application_id" column_invisible="1"/>
    <field name="version_id" column_invisible="1"/>
    <field name="name"/>
    <field name="code"/>
    <field name="route_suffix"/>
    <field name="route_pattern" readonly="1"/>
    <field name="http_methods"/>
    <field name="action_id"
           can_create="0"
           options="{'no_create': True, 'no_quick_create': True, 'no_create_edit': True}"
           context="{
               'list_view_ref': 't4_coreapi.view_ir_actions_server_core_api_picker_list',
           }"/>
    <field name="active"/>
</list>
"""


class CoreApiVersion(models.Model):
    _name = 'core.api.version'
    _description = 'Core API Version'
    _order = 'domain_id, sequence, code'

    name = fields.Char(required=True, translate=True)
    domain_id = fields.Many2one(
        'core.api.domain',
        string='Host Domain',
        required=True,
        ondelete='restrict',
        index=True,
        default=lambda self: self.env['core.api.domain'].get_default().id,
        help='Groups this version under a public hostname, e.g. ashaf.xyz/api/v1.',
    )
    domain_hostname = fields.Char(related='domain_id.hostname', store=True, readonly=True)
    domain_base_url = fields.Char(related='domain_id.base_url', readonly=True)
    code = fields.Char(
        required=True,
        index=True,
        help='URL segment after /api/, e.g. v1 or v2.',
    )
    path_prefix = fields.Char(
        string='API Path',
        compute='_compute_path_prefix',
        store=True,
        help='Path on the host, e.g. /api/v1.',
    )
    public_base_url = fields.Char(
        string='Public Base URL',
        compute='_compute_public_base_url',
        help='Full public base URL including host, e.g. https://ashaf.xyz/api/v1.',
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    endpoint_count = fields.Integer(compute='_compute_endpoint_count')

    _code_unique_per_domain = models.Constraint(
        'unique(domain_id, code)',
        'API version code must be unique per host domain.',
    )

    @api.depends('code')
    def _compute_path_prefix(self):
        """Build the API path from the version code."""
        for rec in self:
            code = (rec.code or '').strip().strip('/')
            rec.path_prefix = f'/api/{code}' if code else '/api'

    @api.depends('domain_id.base_url', 'path_prefix')
    def _compute_public_base_url(self):
        """Build the full public URL for this version."""
        for rec in self:
            base = (rec.domain_id.base_url or '').rstrip('/')
            path = (rec.path_prefix or '/api').rstrip('/')
            rec.public_base_url = f'{base}{path}' if base else path

    @api.depends('code')
    def _compute_endpoint_count(self):
        """Count gateway routes linked to this version."""
        for rec in self:
            rec.endpoint_count = 0
        real_recs = self.filtered('id')
        if not real_recs:
            return
        endpoint_data = self.env['core.api.endpoint'].read_group(
            [('version_id', 'in', real_recs.ids)],
            [],
            ['version_id'],
        )
        counts = {}
        for row in endpoint_data:
            version = row.get('version_id')
            if not version:
                continue
            counts[version[0]] = row.get('version_id_count', row.get('__count', 0))
        for rec in real_recs:
            rec.endpoint_count = counts.get(rec.id, 0)

    @api.model
    def _application_version_tab_xml_name(self, version_id):
        return f'application_form_version_tab_{version_id}'

    @api.model
    def _version_endpoint_field_name(self, version_id):
        return f'x_endpoint_version_{version_id}_ids'

    def _ensure_application_endpoint_field(self):
        """Register a filtered One2many on applications for this API version."""
        self.ensure_one()
        field_name = self._version_endpoint_field_name(self.id)
        model = self.env['ir.model'].sudo().search(
            [('model', '=', 'core.api.application')], limit=1,
        )
        if not model:
            return
        Field = self.env['ir.model.fields'].sudo()
        field = Field.search([
            ('model_id', '=', model.id),
            ('name', '=', field_name),
        ], limit=1)
        vals = {
            'model_id': model.id,
            'name': field_name,
            'field_description': self.display_name or self.name,
            'ttype': 'one2many',
            'relation': 'core.api.endpoint',
            'relation_field': 'application_id',
            'domain': f"[('version_id', '=', {self.id})]",
            'state': 'manual',
        }
        if field:
            field.write(vals)
        else:
            Field.create(vals)

    def _unlink_application_endpoint_field(self):
        """Remove the dynamic application One2many for this API version."""
        self.ensure_one()
        field_name = self._version_endpoint_field_name(self.id)
        model = self.env['ir.model'].sudo().search(
            [('model', '=', 'core.api.application')], limit=1,
        )
        if not model:
            return
        field = self.env['ir.model.fields'].sudo().search([
            ('model_id', '=', model.id),
            ('name', '=', field_name),
        ], limit=1)
        if field:
            field.unlink()

    def _reload_application_model(self):
        """Reload application custom fields and bust cached views."""
        model_names = ['core.api.application']
        self.env.flush_all()
        registry = self.env.registry
        registry._setup_models__(self.env.cr, model_names)
        registry.init_models(
            self.env.cr,
            registry.descendants(model_names, '_inherits'),
            dict(self.env.context, update_custom_fields=True),
        )
        self._clear_application_view_cache()
        self._notify_application_views_changed()

    def _notify_application_views_changed(self):
        """Ask open application forms to reload their view definition."""
        if not self._get_application_form_base_view():
            return
        self.env['bus.bus']._sendone(
            'broadcast',
            'core_api_application_views_changed',
            {},
        )

    def _application_version_tab_arch(self):
        """Build inherited form arch for one per-version routes tab."""
        self.ensure_one()
        page_label = escape(self.display_name or f'API {self.code}')
        field_name = self._version_endpoint_field_name(self.id)
        return f"""<xpath expr="//page[@name='gateway_routes_all']" position="before">
    <page string="{page_label}" name="gateway_routes_{self.id}"
          invisible="domain_id != {self.domain_id.id}">
        <field name="{field_name}" nolabel="1"
               context="{{'default_application_id': id, 'default_domain_id': domain_id, 'default_version_id': {self.id}}}">
            {ENDPOINT_VERSION_TAB_LIST_ARCH}
        </field>
    </page>
</xpath>"""

    @api.model
    def _browse_version_tab_view(self, data):
        """Return the ir.ui.view record linked to an ir.model.data row."""
        if not data or not data.res_id:
            return self.env['ir.ui.view'].browse()
        return self.env['ir.ui.view'].browse(data.res_id)

    def _unlink_application_version_tab_view(self):
        """Remove the inherited application form tab for these versions."""
        IrModelData = self.env['ir.model.data'].sudo()
        for version in self:
            data = IrModelData.search([
                ('module', '=', 't4_coreapi'),
                ('name', '=', self._application_version_tab_xml_name(version.id)),
            ], limit=1)
            if data:
                view = self._browse_version_tab_view(data)
                if view.exists():
                    view.unlink()
                data.unlink()

    @api.model
    def _get_application_form_base_view(self):
        """Return the application form view, if it is already installed."""
        return self.env.ref(APPLICATION_FORM_VIEW_XML_ID, raise_if_not_found=False)

    def _sync_application_version_tab_view(self):
        """Create or update inherited application form tabs for these versions."""
        base_view = self._get_application_form_base_view()
        if not base_view:
            # During module install, version data can load before the form view XML.
            return

        IrUiView = self.env['ir.ui.view'].sudo()
        IrModelData = self.env['ir.model.data'].sudo()

        for version in self:
            xml_name = self._application_version_tab_xml_name(version.id)
            data = IrModelData.search([
                ('module', '=', 't4_coreapi'),
                ('name', '=', xml_name),
            ], limit=1)

            if not version.active:
                if data:
                    view = self._browse_version_tab_view(data)
                    if view.exists():
                        view.unlink()
                    data.unlink()
                version._unlink_application_endpoint_field()
                continue

            version._ensure_application_endpoint_field()

            vals = {
                'name': f'core.api.application.form.version.{version.id}',
                'model': 'core.api.application',
                'inherit_id': base_view.id,
                'mode': 'extension',
                'priority': 15 + (version.sequence or 0),
                'arch': version._application_version_tab_arch(),
            }
            if data:
                view = self._browse_version_tab_view(data)
                if view.exists():
                    view.write(vals)
                else:
                    data.unlink()
                    view = IrUiView.create(vals)
                    IrModelData.create({
                        'name': xml_name,
                        'module': 't4_coreapi',
                        'model': 'ir.ui.view',
                        'res_id': view.id,
                        'noupdate': True,
                    })
            else:
                view = IrUiView.create(vals)
                IrModelData.create({
                    'name': xml_name,
                    'module': 't4_coreapi',
                    'model': 'ir.ui.view',
                    'res_id': view.id,
                    'noupdate': True,
                })

        if self:
            self._reload_application_model()
        else:
            self._clear_application_view_cache()

    def _clear_application_view_cache(self):
        """Bust cached application form views when version tabs change."""
        self.env.registry.clear_cache('templates')

    @api.model
    def sync_all_application_version_tab_views(self):
        """Rebuild every per-version application form tab (install/upgrade)."""
        versions = self.with_context(active_test=False).search([])
        stale_data = self.env['ir.model.data'].sudo().search([
            ('module', '=', 't4_coreapi'),
            ('name', '=like', 'application_form_version_tab_%'),
        ])
        live_names = {
            self._application_version_tab_xml_name(version.id)
            for version in versions
        }
        for data in stale_data:
            if data.name not in live_names:
                view = self._browse_version_tab_view(data)
                if view.exists():
                    view.unlink()
                data.unlink()
        for version in versions.filtered(lambda v: not v.active):
            version._unlink_application_endpoint_field()
        for version in versions.filtered('active'):
            version._ensure_application_endpoint_field()
        versions.filtered('active')._sync_application_version_tab_view()
        versions.filtered(lambda v: not v.active)._unlink_application_version_tab_view()
        apps = self.env['core.api.application'].search([
            ('domain_id', 'in', versions.mapped('domain_id').ids),
        ])
        apps._ensure_version_tabs()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_application_version_tab_view()
        apps = self.env['core.api.application'].search([
            ('domain_id', 'in', records.mapped('domain_id').ids),
        ])
        apps._ensure_version_tabs()
        return records

    def write(self, vals):
        if {'domain_id', 'active', 'sequence', 'code', 'name'} & set(vals):
            result = super().write(vals)
            self._sync_application_version_tab_view()
            return result
        return super().write(vals)

    def unlink(self):
        self._unlink_application_version_tab_view()
        self._unlink_application_endpoint_field()
        self._reload_application_model()
        return super().unlink()

    @api.constrains('code')
    def _check_code(self):
        """Reject empty or slash-containing version codes."""
        for rec in self:
            code = (rec.code or '').strip()
            if not code:
                raise ValidationError(_('API version code is required.'))
            if '/' in code:
                raise ValidationError(_('API version code must not contain slashes.'))

    @api.model
    def get_default_version(self):
        """Return the default active API version (v1 on default domain, or first active)."""
        default_domain = self.env['core.api.domain'].get_default()
        version = self.env.ref('t4_coreapi.core_api_version_v1', raise_if_not_found=False)
        if version and version.active:
            return version
        domain = [('active', '=', True)]
        if default_domain:
            domain.append(('domain_id', '=', default_domain.id))
        return self.search(domain, order='sequence, code', limit=1)

    def action_view_endpoints(self):
        """Open gateway routes filtered to this API version."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gateway Routes'),
            'res_model': 'core.api.endpoint',
            'view_mode': 'list,form',
            'domain': [('version_id', '=', self.id)],
            'context': {'default_version_id': self.id},
        }

    @api.model
    def get_active_by_code(self, code, api_domain=None):
        """Return an active version for code on the given host domain."""
        if not code:
            return self.browse()
        api_domain = api_domain or self.env['core.api.domain'].get_default()
        domain_filter = [('domain_id', '=', api_domain.id)] if api_domain else []
        return self.sudo().search(
            domain_filter + [('code', '=', code), ('active', '=', True)],
            limit=1,
        )

    @api.model
    def resolve_from_api_subpath(self, subpath, api_domain=None):
        """Parse /api/<version>/… using the request host domain.

        Example on ashaf.xyz:
        - subpath ``v1/orders`` -> version v1 on ashaf.xyz domain, suffix orders
        """
        subpath = (subpath or '').strip('/')
        if not subpath:
            return self.browse(), ''

        if api_domain is None:
            api_domain = self.env['core.api.domain'].sudo().get_from_request(
                request.httprequest if request else None
            )

        parts = subpath.split('/')
        version = self.get_active_by_code(parts[0], api_domain=api_domain)
        if version:
            return version, '/'.join(parts[1:])
        return self.browse(), ''
