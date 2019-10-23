from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import config
from odoo import http
from odoo.http import request

import requests
import base64
import logging
import json

_logger = logging.getLogger(__name__)
try:
    import swagger_client
    from swagger_client.rest import ApiException
except ImportError:
    _logger.warning("Marketpay synchronization is not available because the"
                    "`swagger_client` python library cannot be found. Please"
                    "install from: https://github.com/pedroguirao/swagger/")
    swagger_client = None
    ApiException = None


class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(
        selection_add=[
            ('marketpay', 'Marketpay'),
        ],
    )
    marketpay_fee = fields.Float(
        string='Comisión',
        default='0',
    )
    marketpay_currency = fields.Char(
        string='Currency',
        default='978',
    )
    redsys_url = fields.Char()

    @api.model
    def _get_website_url(self):
        """
        For a single website setting the domain website name is not accessible
        for the user, by default is localhost so the system get domain from
        system parameters instead of domain of website record.
        """
        if config['test_enable']:
            return self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url')

        domain = http.request.website.domain
        if domain and domain != 'localhost':
            base_url = '%s://%s' % (
                http.request.httprequest.environ['wsgi.url_scheme'],
                http.request.website.domain
            )
        else:
            base_url = self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url')
        return base_url or ''

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

        # We set configuration of Swagger
        config = swagger_client.Configuration()
        config.host = marketpay_domain
        config.access_token = token
        swagger_client.ApiClient(configuration=config)
        swagger_client.Configuration.set_default(config)
        return True

    @api.multi
    def marketpay_form_generate_values(self, values):
        self.ensure_one()

        marketpay_values = dict(values)

        base_url = self._get_website_url()

        # Marketpay values for the user that do the operation
        marketpaydata = values['partner']

        self._set_swagger_config()

        walletid = marketpaydata.x_marketpaywallet_id
        currency = "EUR"
        amount = str(int(round(values['amount'] * 100)))
        amountfee = self.marketpay_fee

        # Controller URL et in wallet to generate the transaction
        success_url = '%s/wallet/add/money/transaction' % base_url
        # Error URL
        cancel_url = '%s/wallet/error/transaction' % base_url

        apiPayin = swagger_client.PayInsRedsysApi()
        pay_in_id = False
        api_response = False

        fees = swagger_client.Money(amount=amountfee, currency=currency)
        debited = swagger_client.Money(amount=amount, currency=currency)
        redsys_pay = swagger_client.RedsysPayByWebPost(
            credited_wallet_id=walletid, debited_funds=debited, fees=fees,
            success_url=success_url, cancel_url=cancel_url)
        try:
            api_response = apiPayin.pay_ins_redsys_redsys_post_payment_by_web(
                redsys_pay_in=redsys_pay)
            pay_in_id = api_response.pay_in_id
            self.redsys_url = api_response.url

        except ApiException as e:
            print(_("Exception when calling UsersApi->users_post: %s\n" % e))

        PT = request.env['payment.transaction'].sudo()
        tx = PT.search([
            ('is_wallet_transaction', '=', True),
            ('wallet_type', '=', 'credit'),
            ('partner_id', '=', marketpaydata.id),
            ('state', '=', 'draft')], limit=1)

        tx.marketpay_txnid = pay_in_id

        marketpay_values.update({
            'Ds_MerchantParameters': api_response.ds_merchant_parameters,
            'Ds_SignatureVersion': api_response.ds_signature_version,
            'Ds_Signature': api_response.ds_signature,
        })
        return marketpay_values

    @api.multi
    def marketpay_get_form_action_url(self):
        return self.redsys_url


# Transaction No usado en desarrollo para futuros
# Se usa el transaction que viene definido en el módulo wallet

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    marketpay_txnid = fields.Char(
        string='Marketpay ID',
    )

