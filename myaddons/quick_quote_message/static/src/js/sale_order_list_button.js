/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

class SaleOrderListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    async onClickQuickQuote() {
        await this.actionService.doAction("quick_quote_message.action_quick_quote_wizard");
    }
}

export const saleOrderQuickQuoteListView = {
    ...listView,
    Controller: SaleOrderListController,
    buttonTemplate: "quick_quote_message.SaleOrderListView.Buttons",
};

registry.category("views").add("sale_order_quick_quote_list", saleOrderQuickQuoteListView);
