# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from html import escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.t4_coreapi.utils.routing import parse_gateway_subpath

APPLICATION_FORM_VIEW_XML_ID = 't4_coreapi.view_core_api_application_form'

ENDPOINT_VERSION_TAB_LIST_ARCH = """
            <list editable="bottom" decoration-muted="not route_active">
                <field name="application_id" column_invisible="1"/>
                <field name="version_id" column_invisible="1"/>
                <field name="name"/>
                <field name="code"/>
                <field name="route_suffix"/>
                <field name="route_pattern" column_invisible="1"/>
                <field name="public_gateway_url" readonly="1" string="Full Gateway URL"/>
                <field name="http_methods"/>
                <field name="action_id"
                       can_create="0"
                       options="{'no_create': True, 'no_quick_create': True, 'no_create_edit': True}"
                       context="{
                           'list_view_ref': 't4_coreapi.view_ir_actions_server_core_api_picker_list',
                       }"/>
                <field name="route_active"/>
            </list>
            <form string="Gateway Route">
                <field name="application_id" required="1" invisible="1"/>
                <field name="version_id" invisible="1"/>
                <group>
                    <group string="Gateway (public)">
                        <field name="name"/>
                        <field name="code"/>
                        <field name="route_suffix" placeholder="gate1"/>
                        <field name="route_pattern" invisible="1"/>
                        <field name="public_gateway_url" readonly="1" string="Full Gateway URL"/>
                        <field name="http_methods" placeholder="GET,POST"/>
                        <field name="route_active"/>
                    </group>
                    <group string="Handler">
                        <field name="action_id"
                               can_create="0"
                               options="{'no_create': True, 'no_quick_create': True, 'no_create_edit': True, 'no_open': True}"
                               context="{
                                   'create': False,
                                   'edit': False,
                                   'delete': False,
                                   'list_view_ref': 't4_coreapi.view_ir_actions_server_core_api_picker_list',
                               }"/>
                    </group>
                </group>
                <field name="description" placeholder="What this route is for…"/>
            </form>
"""


class CoreApiVersion(models.Model):
    _name = 'core.api.version'
    _description = 'API Version'
    _order = 'sequence, code'

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        index=True,
        help='URL segment after the service code, e.g. v1 in /gk/v1/gate1.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    endpoint_ids = fields.One2many('core.api.endpoint', 'version_id', string='Gateway Routes')
    endpoint_count = fields.Integer(compute='_compute_endpoint_count')

    _code_unique = models.Constraint(
        'unique(code)',
        'API version code must be unique.',
    )

    @api.depends('endpoint_ids')
    def _compute_endpoint_count(self):
        for rec in self:
            rec.endpoint_count = len(rec.endpoint_ids)

    @classmethod
    def _version_endpoint_field_name(cls, version_id):
        return f'x_endpoint_version_{version_id}_ids'

    @classmethod
    def _application_version_tab_xml_name(cls, version_id):
        return f'application_form_version_tab_{version_id}'

    def _ensure_application_endpoint_field(self):
        """Create a dedicated One2many on the application for this version tab."""
        self.ensure_one()
        field_name = self._version_endpoint_field_name(self.id)
        model = self.env['ir.model'].sudo().search(
            [('model', '=', 'core.api.application')], limit=1,
        )
        if not model:
            return False
        IrModelFields = self.env['ir.model.fields'].sudo()
        field = IrModelFields.search([
            ('model_id', '=', model.id),
            ('name', '=', field_name),
        ], limit=1)
        vals = {
            'name': field_name,
            'model_id': model.id,
            'field_description': f'Routes ({self.display_name})',
            'ttype': 'one2many',
            'relation': 'core.api.endpoint',
            'relation_field': 'application_id',
            'domain': f"[('version_id', '=', {self.id})]",
        }
        if field:
            changed = any(
                getattr(field, key) != val for key, val in vals.items()
            )
            if changed:
                field.write(vals)
                return True
            return False
        IrModelFields.create(vals)
        return True

    def _unlink_application_endpoint_field(self):
        """Remove the dynamic One2many field for this version tab."""
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

    def _application_version_tab_arch(self):
        """Build inherited form arch for one per-version routes tab."""
        self.ensure_one()
        page_label = escape(self.display_name or f'API {self.code}')
        field_name = self._version_endpoint_field_name(self.id)
        return f"""<xpath expr="//page[@name='gateway_routes_anchor']" position="before">
    <page string="{page_label}" name="gateway_routes_{self.id}">
        <field name="{field_name}" nolabel="1"
               context="{{'default_application_id': id, 'default_version_id': {self.id}}}">
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
            return

        IrUiView = self.env['ir.ui.view'].sudo()
        IrModelData = self.env['ir.model.data'].sudo()
        model_changed = False

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
                model_changed = True
                continue

            if version._ensure_application_endpoint_field():
                model_changed = True

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

        if model_changed:
            self._reload_application_model()
        elif self:
            self._clear_application_view_cache()
            self._notify_application_views_changed()

    def _clear_application_view_cache(self):
        """Bust cached application form views when version tabs change."""
        self.env.registry.clear_cache('templates')

    def _notify_application_views_changed(self):
        """Ask open application forms to reload their view definition."""
        if not self._get_application_form_base_view():
            return
        self.env['bus.bus']._sendone(
            'broadcast',
            'core_api_application_views_changed',
            {},
        )

    @api.model
    def cleanup_stale_application_version_tab_views(self):
        """Remove inherited version tabs before the base form anchor page changes."""
        IrModelData = self.env['ir.model.data'].sudo()
        stale_data = IrModelData.search([
            ('module', '=', 't4_coreapi'),
            ('name', '=like', 'application_form_version_tab_%'),
        ])
        for data in stale_data:
            view = self._browse_version_tab_view(data)
            if view.exists():
                view.unlink()
            data.unlink()
        self._clear_application_view_cache()

    @api.model
    def _cleanup_stale_dynamic_fields(self):
        """Remove dynamic route fields for API versions that no longer exist."""
        model = self.env['ir.model'].sudo().search(
            [('model', '=', 'core.api.application')], limit=1,
        )
        if not model:
            return False
        live_field_names = {
            self._version_endpoint_field_name(version.id)
            for version in self.with_context(active_test=False).search([('active', '=', True)])
        }
        stale_fields = self.env['ir.model.fields'].sudo().search([
            ('model_id', '=', model.id),
            ('name', '=like', 'x_endpoint_version_%'),
        ])
        removed = False
        for field in stale_fields:
            if field.name not in live_field_names:
                field.unlink()
                removed = True
        return removed

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

        removed_fields = self._cleanup_stale_dynamic_fields()
        model_changed = removed_fields
        for version in versions.filtered(lambda v: not v.active):
            version._unlink_application_endpoint_field()
            model_changed = True
        for version in versions.filtered('active'):
            if version._ensure_application_endpoint_field():
                model_changed = True
        versions.filtered('active')._sync_application_version_tab_view()
        versions.filtered(lambda v: not v.active)._unlink_application_version_tab_view()
        if model_changed:
            self._reload_application_model()
        self.env['core.api.application'].search([])._ensure_version_tabs()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_application_version_tab_view()
        self.env['core.api.application'].search([])._ensure_version_tabs()
        return records

    def write(self, vals):
        if {'active', 'sequence', 'code', 'name'} & set(vals):
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
        """Return the default active API version (v1 XML ref or first active)."""
        version = self.env.ref('t4_coreapi.core_api_version_v1', raise_if_not_found=False)
        if version and version.active:
            return version
        return self.search([('active', '=', True)], order='sequence, code', limit=1)

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
    def get_active_by_code(self, code):
        """Return an active version for the given code."""
        if not code:
            return self.browse()
        return self.sudo().search([('code', '=', code), ('active', '=', True)], limit=1)

    @api.model
    def resolve_from_gateway_subpath(self, subpath):
        """Parse ``v1/gate1`` into version record and remaining route suffix."""
        version_code, rest = parse_gateway_subpath(subpath)
        if not version_code:
            return self.browse(), ''
        version = self.get_active_by_code(version_code)
        return version, rest
