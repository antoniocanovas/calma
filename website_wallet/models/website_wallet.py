import requests
import base64
import json
import swagger_client
from swagger_client.rest import ApiException
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.depends('wallet_transaction.amount', 'wallet_transaction.state')
    def _get_wallet_bal(self):
        for record in self:
            credit_list = [credit.amount for credit in
                           self.mapped('wallet_transaction').filtered(
                               lambda l: l.wallet_type == 'credit' and
                                         l.state == 'done')]
            debit_list = [debit.amount for debit in
                          self.mapped('wallet_transaction').filtered(
                              lambda l: l.wallet_type == 'debit' and
                                        l.state == 'done')]
            record.update({
                'wallet_balance': sum(credit_list) - sum(debit_list)
            })

    wallet_balance = fields.Monetary(
        string='Wallet Balance',
        store=True,
        readonly=True,
        compute='_get_wallet_bal',
    )
    wallet_transaction = fields.One2many(
        comodel_name='payment.transaction',
        inverse_name='partner_id',
        string='Wallet Transaction',
        domain=[('is_wallet_transaction', '=', True)],
    )


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    is_wallet_transaction = fields.Boolean(
        string='Is Wallet Transaction',
    )
    wallet_type = fields.Selection(
        selection=[
            ('credit', 'Credit'),
            ('debit', 'Debit'),
        ],
        string='Wallet Process',
    )

    def get_next_wallet_reference(self):
        reference = self.env['ir.sequence'].next_by_code(
            'payment.wallet.transaction')
        return reference

    def _check_or_create_sale_tx(self, order, acquirer, payment_token=None,
                                 tx_type='form', add_tx_values=None,
                                 reset_draft=True):
        tx = self
        if not tx:
            tx = self.search([('reference', '=', order.name)], limit=1)

        if tx.state in ['error', 'cancel']:  # filter incorrect states
            tx = False
        if (tx and tx.acquirer_id != acquirer) or (
                order not in tx and tx.sale_order_ids):  # filter unmatching
            tx = False
        if tx and payment_token and tx.payment_token_id and \
                payment_token != tx.payment_token_id:  # new or distinct token
            tx = False

        remaining_amount = order.amount_total
        if order.wallet_txn_id:
            remaining_amount -= order.wallet_txn_id.amount

        # still draft tx, no more info -> rewrite on tx or create a new one
        # depending on parameter
        if tx and tx.state == 'draft':
            if reset_draft:
                tx.write(dict(
                    self.on_change_partner_id(order.partner_id.id).get(
                        'value', {}),
                    amount=remaining_amount,
                    type=tx_type)
                )
            else:
                tx = False

        if not tx:
            tx_values = {
                'acquirer_id': acquirer.id,
                'type': tx_type,
                'amount': remaining_amount,
                'currency_id': order.pricelist_id.currency_id.id,
                'partner_id': order.partner_id.id,
                'partner_country_id': order.partner_id.country_id.id,
                'reference': self.get_next_reference(order.name),
                'sale_order_ids': [(4, order.id)],
            }
            if add_tx_values:
                tx_values.update(add_tx_values)
            if payment_token and payment_token.sudo().partner_id == \
                    order.partner_id:
                tx_values['payment_token_id'] = payment_token.id

            tx = self.create(tx_values)

        # update quotation
        order.write({
            'payment_tx_id': tx.id,
        })
        return tx

    def render_sale_button(self, order, submit_txt=None, render_values=None):
        values = {
            'partner_id':
                order.partner_shipping_id.id or order.partner_invoice_id.id,
            'billing_partner_id': order.partner_invoice_id.id,
        }
        if render_values:
            values.update(render_values)

        remaining_amount = order.amount_total
        if order.wallet_txn_id:
            remaining_amount -= order.wallet_txn_id.amount

        # Not very elegant to do that here but no choice regarding the design.
        self._log_payment_transaction_sent()
        return self.acquirer_id.with_context(
            submit_class='btn btn-primary', submit_txt=submit_txt or
                                                       _('Pay Now')
        ).sudo().render(
            self.reference,
            remaining_amount,
            order.pricelist_id.currency_id.id,
            values=values,
        )


class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    is_wallet_acquirer = fields.Boolean(
        string='Is Wallet Acquirer',
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_wallet_product = fields.Boolean(
        string='Is Wallet Product',
    )


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    wallet_txn_id = fields.Many2one(
        comodel_name='payment.transaction',
        string='Wallet Transaction',
        on_delete='set null',
        copy=False,
    )
    partner_wallet_balance = fields.Monetary(
        string='Wallet Balance',
        related='partner_id.wallet_balance',
        readonly=True,
    )

    @api.multi
    def action_wallet_pay(self):
        for order in self.filtered(lambda l: l.state in ['draft', 'sent']):
            if order.partner_wallet_balance >= \
                    order.amount_total:
                tx_amount = order.amount_total
            if order.partner_wallet_balance < \
                    order.amount_total:
                raise ValidationError(
                    _('Código o Número de autorización definido'))

            if order.wallet_txn_id:
                tx = order.wallet_txn_id
                tx.amount = tx_amount
            else:
                acquirer = self.env['payment.acquirer'].sudo().search([
                    ('is_wallet_acquirer', '=', True)], limit=1)
                if not acquirer:
                    raise UserError(_('No acquirer configured. Please create '
                                      'wallet acquirer.'))
                values = {
                    'acquirer_id': acquirer.id,
                    'type': 'form',
                    'amount': tx_amount,
                    'currency_id': order.company_id.currency_id.id,
                    'partner_id': order.partner_id.id,
                    'partner_country_id': order.partner_id.country_id.id,
                    'is_wallet_transaction': True,
                    'wallet_type': 'debit',
                    'sale_order_ids': [(4, order.id)],
                    'reference':
                        self.env['payment.transaction'].get_next_wallet_reference(),
                }
                tx = self.env['payment.transaction'].sudo().create(values)
                order.wallet_txn_id = tx.id
                self.action_marketpay_wallet(order)
                self.action_product_update(order)
        return True

    @api.multi
    def _prepare_marketpay_key(self):
        self.ensure_one()
        marketpay_key = self.env.user.company_id.marketpay_key
        marketpay_secret = self.env.user.company_id.marketpay_secret
        if not marketpay_key or not marketpay_secret:
            raise ValidationError(
                _("You must set MarketPay's key and secret in company form."))
        secret = '%s:%s' % (marketpay_key, marketpay_secret)
        return "Basic %s" % base64.b64encode(secret.encode()).decode('ascii')

    @api.multi
    def _set_swagger_config(self):
        self.ensure_one()
        key = self._prepare_marketpay_key()
        token_url = self.env.user.company_id.token_url
        marketpay_domain = self.env.user.company_id.marketpay_domain

        data = {'grant_type': 'client_credentials'}
        headers = {'Authorization': key,
                   'Content-Type': 'application/x-www-form-urlencoded'}

        r = requests.post(token_url, data=data, headers=headers)
        rs = r.content.decode()
        response = json.loads(rs)
        token = response['access_token']

        config = swagger_client.Configuration()
        config.host = marketpay_domain
        config.access_token = token
        swagger_client.ApiClient(configuration=config)
        swagger_client.Configuration.set_default(config)
        return True

    @api.multi
    def action_marketpay_wallet(self,order):
        credited_wallet_id = order.order_line[0].product_id.project_wallet
        acquirer = self.env['payment.acquirer'].sudo().search([
            ('is_wallet_acquirer', '=', True)], limit=1)
        if not acquirer:
            raise UserError(
                _('No acquirer configured. Please create wallet acquirer.'))

        self._set_swagger_config()
        currency = "EUR"
        amount = str(int(round(order.amount_total * 100)))
        amountfee = acquirer.marketpay_fee

        # create an instance of the API class
        api_instance = swagger_client.TransfersApi()

        fees = swagger_client.Money(amount=amountfee, currency=currency)
        debited_founds = swagger_client.Money(amount=amount, currency=currency)
        credited_user_id = order.partner_id.x_marketpayuser_id
        debited_wallet_id= order.partner_id.x_marketpaywallet_id

        transfer = swagger_client.TransferPost(
            credited_user_id=credited_user_id,
            debited_funds=debited_founds,
            credited_wallet_id=credited_wallet_id,
            debited_wallet_id=debited_wallet_id,
            fees=fees)
        try:
            api_response = api_instance.transfers_post(transfer=transfer)
        except ApiException as e:
            print("Exception when calling UsersApi->users_post: %s\n" % e)
        return True

    @api.multi
    def action_product_update(self, order):
        order_line = order.order_line[0]
        product = order.order_line[0].product_id
        product.invertido = product.invertido + order.amount_total
        product.inversores = product.inversores + 1
        return True

    @api.multi
    def unlink(self):
        for order in self:
            if order.state != 'draft':
                raise UserError(_('You can only delete draft quotations!'))
            # Remove Wallet Transaction
            if order.wallet_txn_id:
                order.wallet_txn_id.unlink()
        return super(SaleOrder, self).unlink()

    @api.multi
    def _create_payment_transaction(self, vals):
        transaction = super(SaleOrder, self)._create_payment_transaction(vals)
        if self.wallet_txn_id and self.wallet_txn_id.amount:
            transaction.amount = sum(self.mapped('amount_total')) - \
                                 self.wallet_txn_id.amount
        return transaction
