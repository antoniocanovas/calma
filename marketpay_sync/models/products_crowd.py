from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.osv import osv
import requests
import base64
import json
import swagger_client
from swagger_client.rest import ApiException


class ProductsCrowd(models.Model):
    _inherit = "product.template"

    crowdfunding = fields.Boolean(string='Es crowdfunding')
    zona = fields.Char('Zona')
    crfd = fields.Char('Alcance CRFD')
    tipo_inversion = fields.Many2one(String='Tipo Inversión',comodel_name='crowfunding_opciones',domain=('tipo','=','inversion'))
    riesgo_inversion = fields.Many2one(String='Riesgo Inversión',comodel_name='crowfunding_opciones',domain=('tipo','=','riesgo'))
    pais = fields.Many2one('crowfunding_opciones',String='País',domain=(
        'tipo','=','pais'))
    financiacion_bancaria = fields.Many2one(String='Financiación Bancaria',comodel_name='crowfunding_opciones',
                                            domain=('tipo','=','financiacion'))
    premium = fields.Many2one(String='Premium',comodel_name='crowfunding_opciones',domain=('tipo','=','premium'))
    objetivo_crowfunding = fields.Float('Objetivo Crowfunding')
    invertido = fields.Float('Invertido')
    porcentaje_crowfunding = fields.Float('Porcentaje Crowfunding',compute='_calcula_invertido')
    inversores = fields.Integer('Inversores')
    plazo_inversion = fields.Char('Plazo Inversión')
    rentabilidad_anual = fields.Char('Rentabilidad Anual')
    tir_historico = fields.Char('TIR Histórico')
    rentabilidad_total = fields.Char('Rentabilidad Total')
    project_wallet = fields.Char('Wallet de Proyecto')
    mapa = fields.Binary('Mapa')
    rentabilidad_real = fields.Char('Rentabilidad Real')

    @api.depends('invertido')
    def _calcula_invertido(self):
        for record in self:
            if record.objetivo_crowfunding != 0:
                record.porcentaje_crowfunding = (
                                                        record.invertido*100)/record.objetivo_crowfunding

    @api.multi
    def _check_wallet(self):
        company = self.env['res.company']._company_default_get('product.template')
        company_marketpay_id = company.marketpayuser_id
        if company_marketpay_id == False:
            raise osv.except_osv(('Marketpay ID no definido para la empresa'), ('Primero debe crear una compañía con MarketpayId'))
        return


    @api.model
    def create(self, values):
        record = super(ProductsCrowd, self).create(values)
        marketpay_key = "73a4d867-aeec-4e89-a295-64f14dc25ab9"
        marketpay_secret = "kFNm3CQU-ynHaM5g4OZ4MsSxOqmM85j4lgOVLkCgQYY="
        marketpay_domain = "https://api-sandbox.marketpay.io"

        #CLiente swagger conf

        token_url = 'https://api-sandbox.marketpay.io/v2.01/oauth/token'
        key = 'Basic %s' % base64.b64encode(
            b'73a4d867-aeec-4e89-a295-64f14dc25ab9:kFNm3CQU-ynHaM5g4OZ4MsSxOqmM85j4lgOVLkCgQYY=').decode('ascii')
        data = {'grant_type': 'client_credentials'}
        headers = {'Authorization': key, 'Content-Type': 'application/x-www-form-urlencoded'}

        r = requests.post(token_url, data=data, headers=headers)

        rs = r.content.decode()
        response = json.loads(rs)
        token = response['access_token']

        # Default conf for Swagger
        config = swagger_client.Configuration()
        config.host = marketpay_domain
        config.access_token = token
        client = swagger_client.ApiClient(configuration=config)
        api_instance = swagger_client.Configuration.set_default(config)
        apiUser = swagger_client.UsersApi()

        ###########Create wallet for Company  user########################

        company = self.env['res.company']._company_default_get('product.template')

        apiWallet = swagger_client.WalletsApi()
        ownersList = [company.marketpayuser_id]
        wallet = swagger_client.WalletPost(owners=ownersList, description="wallet en EUR", currency='EUR')

        try:

            api_response = apiWallet.wallets_post(wallet=wallet)
            record['project_wallet']= api_response.id
        except ApiException as e:
            print("Exception when calling WalletApi->Wallet_post: %s\n" % e)
        return record