from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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
    rentabilidad_anual = fields.Char()
    tir_historico = fields.Char(
        string='TIR Histórico',
    )
    rentabilidad_total = fields.Char()
    project_wallet = fields.Char(
        string='Wallet de Proyecto',
        readonly=True,
    )
    mapa = fields.Binary()
    rentabilidad_real = fields.Char()
    inversion_minima = fields.Float(
        string='Inversión Mínima',
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
            if product.cowdfunding and not product.project_wallet:
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
