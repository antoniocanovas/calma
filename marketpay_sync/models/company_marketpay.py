import requests
import base64
import json
import swagger_client
from swagger_client.rest import ApiException
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.osv import osv


class marketpay_company(models.Model):
    _inherit = 'res.company'

    marketpayuser_id= fields.Char(string="Marketpay ID")
    #marketpaywallet_id = fields.Char(string="Marketpay Wallet")
    x_nombreprovincia_id = fields.Char(string="Código Región",related='state_id.name')
    x_codigopais_id = fields.Char(string="Código País",related='country_id.code')


    @api.multi
    def _get_wallet(self):
        # Marketpay vars

        marketpay_key = "73a4d867-aeec-4e89-a295-64f14dc25ab9"
        marketpay_secret = "kFNm3CQU-ynHaM5g4OZ4MsSxOqmM85j4lgOVLkCgQYY="
        marketpay_domain = "https://api-sandbox.marketpay.io"

        # CLient config

        token_url = 'https://api-sandbox.marketpay.io/v2.01/oauth/token'
        key = 'Basic %s' % base64.b64encode(
            b'73a4d867-aeec-4e89-a295-64f14dc25ab9:kFNm3CQU-ynHaM5g4OZ4MsSxOqmM85j4lgOVLkCgQYY=').decode('ascii')
        data = {'grant_type': 'client_credentials'}
        headers = {'Authorization': key, 'Content-Type': 'application/x-www-form-urlencoded'}

        r = requests.post(token_url, data=data, headers=headers)

        rs = r.content.decode()
        response = json.loads(rs)
        token = response['access_token']

        # Configuración default de Swagger
        config = swagger_client.Configuration()
        config.host = marketpay_domain
        config.access_token = token
        client = swagger_client.ApiClient(configuration=config)
        api_instance = swagger_client.Configuration.set_default(config)
        apiUser = swagger_client.UsersApi()

        ############# Funcition Create User and Wallet #####################

        address = swagger_client.Address(address_line1=self.street, address_line2=self.street2,
                                         city=self.city, postal_code=self.zip,
                                         country=self.x_codigopais_id, region=self.x_nombreprovincia_id)

        user_natural = swagger_client.UserNaturalPost(address=address)
        user_natural.email = self.email
        user_natural.first_name = self.name
        # user_natural.occupation = self.function']
        # user_natural.tag = self.comment']
        user_natural.country_of_residence = self.x_codigopais_id
        user_natural.nationality = self.x_codigopais_id

        try:

            api_response = apiUser.users_post_natural(user_natural=user_natural)
            self.marketpayuser_id = api_response.id


        except ApiException as e:
            print("Exception when calling UsersApi->users_post: %s\n" % e)

    @api.multi
    def marketpay_validate(self):

        if self.x_codigopais_id == False:
            raise osv.except_osv(('x_codigopais_id'),
                                 ('El campo pais es obligatorio'))
        if self.x_nombreprovincia_id == False:
            raise osv.except_osv(('x_nombreprovincia_id'),
                                 ('El campo provincia es obligatorio'))
        if self.email == False:
            raise osv.except_osv(('email'),
                                 ('El campo mail es obligatorio'))
        if self.city == False:
            raise osv.except_osv(('city'),
                                 ('El campo ciudad es obligatorio'))
        if self.street == False:
            raise osv.except_osv(('street'),
                                 ('El campo calle es obligatorio'))
        if self.zip == False:
            raise osv.except_osv(('zip'),
                                 ('El campo C.P es obligatorio'))

        self._get_wallet()