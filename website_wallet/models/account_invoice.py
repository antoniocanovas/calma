from odoo import _, api, models
from odoo.exceptions import UserError


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_invoice_paid(self):
        res = super(AccountInvoice, self).action_invoice_paid()
        sale_obj = self.env['sale.order']
        pay_obj = self.env['payment.transaction']
        # refund to wallet when paid invoice
        for inv in self:
            if inv.type not in ['in_refund', 'out_refund']:
                continue
            if not self.origin:
                continue
            origin_invoice_id = self.search([('number', '=', self.origin)])
            if not origin_invoice_id:
                continue
            sale_order_id = sale_obj.search(
                [('name', '=', origin_invoice_id.origin)])
            if not sale_order_id.wallet_txn_id:
                continue
            acquirer = self.env['payment.acquirer'].sudo().search([
                ('is_wallet_acquirer', '=', True)], limit=1)
            if not acquirer:
                raise UserError(_('No acquirer configured. Please create '
                                  'wallet acquirer.'))
            values = {
                'acquirer_id': acquirer.id,
                'type': 'form',
                'amount': sale_order_id.wallet_txn_id.amount,
                'currency_id': sale_order_id.company_id.currency_id.id,
                'partner_id': sale_order_id.partner_id.id,
                'partner_country_id': sale_order_id.partner_id.country_id.id,
                'is_wallet_transaction': True,
                'wallet_type': 'credit',
                'sale_order_id': sale_order_id.id,
                'reference': pay_obj.get_next_wallet_reference(),
            }
            tx = pay_obj.sudo().create(values)
            tx.state = 'done'
        return res
