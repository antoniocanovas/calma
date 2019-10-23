from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.multi
    def write(self, values):
        if self.product_id.crowdfunding and \
                values.get('product_uom_qty', 0) != 1:
            if any([field_name in values for field_name in
                    ['price_unit', 'product_id', 'order_id']]):
                values['price_unit'] = values['product_uom_qty']
                values['product_uom_qty'] = 1.0
        return super().write(values)
