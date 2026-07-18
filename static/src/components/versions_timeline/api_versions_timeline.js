/** @odoo-module **/

import { Domain } from "@web/core/domain";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { statusBarField, StatusBarField } from "@web/views/fields/statusbar/statusbar_field";

export class ApiVersionsTimeline extends StatusBarField {
    static template = "t4_coreapi.VersionsTimeline";

    /** @override **/
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");
    }

    /** @override **/
    getDomain(props) {
        return Domain.and([
            super.getDomain(props),
            [["service_id", "=", props.record.evalContext.id]],
        ]).toList();
    }

    async onClickAddVersionBtn() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Create Version',
            res_model: 't4.coreapi.version',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: {
                default_service_id: this.props.record.evalContext.id,
            },
        }, {
            onClose: async () => {
                const versions = await this.orm.searchRead('t4.coreapi.version', [['service_id', '=', this.props.record.resId]], ['id'], { order: 'id desc', limit: 1 });
                if (versions.length > 0) {
                    await this.props.record.model.load({
                        context: {
                            ...this.props.record.model.env.searchModel.context,
                            version_id: versions[0].id,
                        }
                    });
                } else {
                    this.props.record.load();
                }
            }
        });
    }

    /** @override **/
    async selectItem(item) {
        const { record } = this.props;
        await record.save();
        await this.props.record.model.load({
            context: {
                ...this.props.record.model.env.searchModel.context,
                version_id: item.value,
            },
        });
    }

    /** @override **/
    getAllItems() {
        const items = super.getAllItems();
        return items.map((item, index) => {
            return {
                ...item,
                toolTip: item.label,
            };
        });
    }
}

export const apiVersionsTimeline = {
    ...statusBarField,
    component: ApiVersionsTimeline,
    additionalClasses: ["o_field_statusbar", "d-flex", "gap-1"],
};

registry.category("fields").add("api_versions_timeline", apiVersionsTimeline);
