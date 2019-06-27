

import requests
import base64
import logging
import urllib
import json
import swagger_client
from swagger_client.rest import ApiException
from odoo import models, fields, api
from odoo.tools import config
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.addons import decimal_precision as dp
from odoo.tools.float_utils import float_compare
from odoo import exceptions
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)



class AcquirerMarketpay(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('marketpay', 'Marketpay')])
    x_marketpay_key = fields.Char('Key', required=True)
    x_marketpay_secret = fields.Char('secret', required=True)
    x_marketpay_domain = fields.Char('domain', required=True)
    x_marketpay_fee = fields.Integer('Comisión', required=True)
    x_marketpay_currency = fields.Char('Currency', default='978',
                                       required_if_provider='marketpay')
    x_redsys_url = fields.Char()


    @api.model
    def _get_website_url(self):
        """
        For a single website setting the domain website name is not accesible
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
    def marketpay_form_generate_values(self, values):
        self.ensure_one()
        marketpay_values = dict(values)

        base_url = self._get_website_url()
        #callback_url = self._get_website_callback_url()

        ## valores de marketpay para el usuario que hace la Operación ###
        marketpaydata = values['partner']

        # Configuración CLiente
        encoded = self.x_marketpay_key + ":" + self.x_marketpay_secret

        token_url = 'https://api-sandbox.marketpay.io/v2.01/oauth/token'

        key = 'Basic %s' % base64.b64encode(encoded.encode('ascii')).decode('ascii')
        data = {'grant_type': 'client_credentials'}
        headers = {'Authorization': key, 'Content-Type': 'application/x-www-form-urlencoded'}

        r = requests.post(token_url, data=data, headers=headers)

        rs = r.content.decode()
        response = json.loads(rs)
        token = response['access_token']

        #### Cargamos Configuración default de Swagger
        config = swagger_client.Configuration()
        config.host = self.x_marketpay_domain
        config.access_token = token
        client = swagger_client.ApiClient(configuration=config)
        api_instance = swagger_client.Configuration.set_default(config)

        ############ trae los valores del partner ############

        # merchant_parameters = self._prepare_merchant_parameters(values)

        # walletid = marketpaydata.x_marketpaywallet_id
        # userid = marketpaydata.x_marketpayuser_id

        walletid = "9347379"
        userid = "9347382"

        currency = "EUR"
        amount = str(int(round(values['amount'] * 100)))
        amountfee = self.x_marketpay_fee

       #### URL del controler definido en wallet para generar el .transaction ####
        success_url = '%s/wallet/add/money/transaction' % base_url
       #### URL de error pendiente de definir ####
        cancel_url = '%s/wallet/error/transaction' % base_url

        apiPayin = swagger_client.PayInsRedsysApi()

        fees = swagger_client.Money(amount=amountfee, currency=currency)
        debited = swagger_client.Money(amount=amount, currency=currency)
        redsys_pay = swagger_client.RedsysPayByWebPost(credited_wallet_id=walletid, debited_funds=debited, fees=fees,
                                                       success_url=success_url, cancel_url=cancel_url)

        try:

            api_response = apiPayin.pay_ins_redsys_redsys_post_payment_by_web(redsys_pay_in=redsys_pay)


        except ApiException as e:
            print("Exception when calling UsersApi->users_post: %s\n" % e)

        #print(api_response)

        pay_in_id = api_response.pay_in_id
        self.x_redsys_url = api_response.url


        PT = request.env['payment.transaction'].sudo()
        tx = PT.search([
            ('is_wallet_transaction', '=', True), ('wallet_type', '=', 'credit'),
            ('partner_id', '=', marketpaydata.id), ('state', '=', 'draft')], limit=1)


        tx.marketpay_txnid = pay_in_id

        #print(tx)

        marketpay_values.update({

            'Ds_MerchantParameters': api_response.ds_merchant_parameters,
            'Ds_SignatureVersion': api_response.ds_signature_version,
            'Ds_Signature': api_response.ds_signature,


        })

        return marketpay_values


    @api.multi
    def marketpay_get_form_action_url(self):
        return self.x_redsys_url


######## Trnasaction No usado en desarrollo para futuros ####
######## Se usa el transaction que vienee definido en el módulo wallet ###

class TxMarketpay(models.Model):
    _inherit = 'payment.transaction'


    marketpay_txnid = fields.Char('Marketpay ID')


    def merchant_params_json2dict(self, data):
        parameters = data.get('Ds_MerchantParameters', '')
        return json.loads(base64.b64decode(parameters).decode())

    # --------------------------------------------------
    # No Usado en proyecto CALMA
    # No en producción, definidas funciones para una posible implementación
    # de hacer el transaction desde marketpay en lugar del wallet
    # --------------------------------------------------

    @api.model
    def _marketpay_form_get_tx_from_data(self, data):

        print("################RESULT FORM #####################")

        pedido = data['order']
        reference = pedido.transaction_ids[0].reference
        print(reference)
        tx = self.search([('reference', '=', reference)])
        print(tx)

        return tx

    @api.multi
    def _marketpay_form_get_invalid_parameters(self, data):

        test_env = http.request.session.get('test_enable', False)
        invalid_parameters = []

        if invalid_parameters and test_env:
            return []
        return invalid_parameters

    @api.multi
    def _marketpay_form_validate(self, data):

        #Tomamos la id de paymenttransaction

        pedido = data['order']
        reference = pedido.transaction_ids[0].reference
        tx = self.search([('reference', '=', reference)])


        # create an instance of the API class
        api_instance = swagger_client.PayInsRedsysApi()
        pay_in_id = tx.redsys_txnid  # int | The Id of a payment
        print(pay_in_id)

        try:

            api_response = api_instance.pay_ins_redsys_redsys_get_payment(pay_in_id)
            print(api_response)
        except ApiException as e:
            print("Exception when calling PayInsRedsysApi->pay_ins_redsys_redsys_get_payment: %s\n" % e)


        print("vamos!!")
        print(api_response.status)

        if api_response.status == "SUCCEEDED":
            print("dentro del if")
            self.write({
                'state': 'done',
                'state_message': 'Ok',
            })

            print("escrito el estado del pedido")
            return True

        if api_response.status == "FAILED":

            self.write({
                'state': 'cancel',
                'state_message': 'Bank Error'

            })
            return False


    @api.model
    def form_feedback(self, data, acquirer_name):

        res = super(TxMarketpay, self).form_feedback(data, acquirer_name)


        try:
            tx_find_method_name = '_%s_form_get_tx_from_data' % acquirer_name
            if hasattr(self, tx_find_method_name):
                tx = getattr(self, tx_find_method_name)(data)
            _logger.info(
                '<%s> transaction processed: tx ref:%s, tx amount: %s',
                acquirer_name, tx.reference if tx else 'n/a',
                tx.amount if tx else 'n/a')

        except Exception:
            _logger.exception(
                'Fail to confirm the order or send the confirmation email%s',
                tx and ' for the transaction %s' % tx.reference or '')
        return res
