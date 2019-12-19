from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
from datetime import datetime

import requests
import json
import swagger_client
from swagger_client.rest import ApiException

from .crowdfunding_options import OPTIONS


class ProductTemplate(models.Model):
    _inherit = "product.template"

    crowdfunding = fields.Boolean(
        string='Es crowdfunding',
    )
    zona = fields.Char()
    crfd = fields.Char(
        string='Alcance CRFD',
    )
    tipo_inversion = fields.Many2one(
        comodel_name='crowdfunding.options',
        domain=[('crowdfunding_type', '=', OPTIONS[0][0])],
    )
    riesgo_inversion = fields.Many2one(
        comodel_name='crowdfunding.options',
        domain=[('crowdfunding_type', '=', OPTIONS[1][0])],
    )
    pais = fields.Many2one(
        comodel_name='crowdfunding.options',
        domain=[('crowdfunding_type', '=', OPTIONS[2][0])],
    )
    financiacion_bancaria = fields.Many2one(
        comodel_name='crowdfunding.options',
        domain=[('crowdfunding_type', '=', OPTIONS[3][0])],
    )
    premium = fields.Many2one(
        comodel_name='crowdfunding.options',
        domain=[('crowdfunding_type', '=', OPTIONS[4][0])],
    )
    objetivo_crowdfunding = fields.Float()
    porcentaje_crowdfunding = fields.Float(
        compute='_compute_porcentaje_crowdfunding',
    )
    plazo_inversion = fields.Char()
    rentabilidad_anual = fields.Float()
    tir_historico = fields.Float(
        string='TIR Histórico',
    )
    rentabilidad_total = fields.Float()
    project_wallet = fields.Char(
        string='Wallet de Proyecto',
        readonly=True,
    )
    mapa = fields.Binary()
    rentabilidad_real = fields.Float()
    inversion_minima = fields.Float(
        string='Inversión Mínima',
        default=1.0,
    )
    sale_line_ids = fields.One2many(
        string='Sale lines',
        comodel_name='sale.order.line',
        inverse_name='product_id',
    )
    invertido = fields.Float(
        compute='_compute_investments_count',
    )
    inversores = fields.Integer(
        compute='_compute_investments_count',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('crowdfunding', 'Crowdfunding'),
            ('in_execution', 'In Execution'),
            ('return', 'In Refund'),
            ('closed', 'Closed'),
        ],
        default='draft',
    )

    def _get_sale_lines(self, domain):
        # To easy filter sale order lines
        sale_order_line = self.env['sale.order.line']
        domain += [('is_investment', '=', True)]
        return sale_order_line.search(domain)

    @api.depends('sale_line_ids.price_subtotal',
                 'sale_line_ids.order_id.partner_id')
    def _compute_investments_count(self):
        for product in self:
            sale_lines = self._get_sale_lines(
                [('product_id', 'in', product.product_variant_ids.ids)])
            product.invertido = sum(sale_lines.mapped('price_subtotal'))
            product.inversores = len(sale_lines.mapped('order_id.partner_id'))

    @api.multi
    def action_view_sale_lines(self):
        sale_lines = self._get_sale_lines(
            [('product_id', '=', self.product_variant_ids.id)])
        action = self.env.ref(
            'calma_grid.action_sales_order_line_calma').read()[0]
        action['domain'] = [('id', 'in', sale_lines.ids)]
        return action

    @api.depends('invertido', 'objetivo_crowdfunding')
    def _compute_porcentaje_crowdfunding(self):
        for record in self:
            if record.objetivo_crowdfunding:
                record.porcentaje_crowdfunding = \
                    (record.invertido * 100) / record.objetivo_crowdfunding

    @api.multi
    def _check_wallet(self):
        if not self.env.user.company_id.marketpayuser_id:
            raise ValidationError(
                _('Primero debe crear una compañía con MarketpayId'))

    @api.constrains('crowdfunding')
    def _create_wallet(self):
        for product in self:
            if product.crowdfunding and not product.project_wallet:
                marketpay_domain = self.env.user.company_id.marketpay_domain
                token_url = self.env.user.company_id.token_url
                key = self.env.user.company_id._prepare_marketpay_key()
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
                swagger_client.UsersApi()

                apiWallet = swagger_client.WalletsApi()
                ownersList = [self.env.user.company_id.marketpayuser_id]
                wallet = swagger_client.WalletPost(
                    owners=ownersList,
                    description="wallet en EUR",
                    currency='EUR')
                try:
                    api_response = apiWallet.wallets_post(wallet=wallet)
                    product.project_wallet = api_response.id
                except ApiException as e:
                    print("Exception when calling WalletApi->Wallet_post: "
                          "%s\n" % e)
    ### REFUND METHODS ###
    @api.multi
    def check_founds(self, wallet_id):
        if not self.rentabilidad_real:
            raise ValidationError(_('El campo rentabilidad real no contiene datos'))
            total_refund = ((((self.rentabilidad_real) / 100) * self.invertido) + self.invertido) * 100
            apiWallet = swagger_client.WalletsApi()

            try:
                api_response = apiWallet.wallets_get(wallet_id)
                wallet_balance_cents = api_response.balance.amount
            except ApiException as e:
                print("Exception when calling WalletsApi->wallets_get: %s\n" % e)

            if total_refund > wallet_balance_cents:
                raise ValidationError(_('No hay fondos para hacer la operación'))
            else:
                return

    @api.multi
    def create_credit_pt(self, partner, amount, acquirer):
        PA = self.env['payment.acquirer'].sudo()
        PT = self.env['payment.transaction'].sudo()
        tx = PT.search([
                ('is_wallet_transaction', '=', True),
                ('wallet_type', '=', 'credit'),
                ('partner_id', '=', partner.id),
                ('state', '=', 'draft')], limit=1)
        if tx:
                tx.amount = amount
                tx.acquirer_id = acquirer.id
                tx.state = 'done'
                tx.date = datetime.now()
        else:
                PT.create({
                    'acquirer_id': acquirer.id,
                    'type': 'form',
                    'amount': amount,
                    'currency_id': acquirer.company_id.currency_id.id,
                    'partner_id': partner.id,
                    'partner_country_id': partner.country_id.id,
                    'is_wallet_transaction': True,
                    'wallet_type': 'credit',
                    'reference': self.env[
                        'payment.transaction'].sudo().get_next_wallet_reference(),
                    'state': 'done',
                    'date': datetime.now()
                })

    @api.multi
    def wallet_transfer(self, amount_to_tranfer, investor, investor_market_id, investor_market_wallet):
        credited_wallet_id = investor_market_wallet
        acquirer = self.env['payment.acquirer'].sudo().search([
            ('is_wallet_acquirer', '=', True)], limit=1)
        if not acquirer:
            raise UserError(
                _('No acquirer configured. Please create wallet acquirer.'))

        currency = "EUR"
        amount = str(int(round(amount_to_tranfer * 100)))
        amountfee = acquirer.marketpay_fee

        # create an instance of the API class
        api_instance = swagger_client.TransfersApi()

        fees = swagger_client.Money(amount=amountfee, currency=currency)
        debited_founds = swagger_client.Money(amount=amount, currency=currency)
        credited_user_id = investor_market_id
        debited_wallet_id = self.project_wallet

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
            # Make a credit Wallet transaction for user
        self.create_credit_pt(investor, amount_to_tranfer, acquirer)
        return True

    @api.multi
    def pay_investors(self):
        # Set swagger Config
        self.env.user.company_id._set_swagger_config()
        #Check if enought € in project wallet for refund
        self.check_founds(self.project_wallet)

        for line in self.sale_line_ids:
            if line.refund_done == False:
                investor = line.order_partner_id
                investor_market_id = investor.x_marketpayuser_id
                investor_market_wallet = investor.x_marketpaywallet_id
                # Get amount to transfer for this Line
                amount_to_tranfer = ((((self.rentabilidad_real) / 100) * line.price_subtotal) + line.price_subtotal)
                # Make te transfer
                self.wallet_transfer(amount_to_tranfer, investor, investor_market_id, investor_market_wallet)
                line.refund_done = True


