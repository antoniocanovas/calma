
from swagger_client.rest import ApiException
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.osv import osv
import tempfile
import os
from os import path
import requests
import base64
import json
import swagger_client

class x_marketpayuser(models.Model):
    _inherit = 'res.partner'

    x_marketpayuser_id = fields.Char(string="Marketpay User")
    x_marketpaywallet_id = fields.Char(string="Marketpay Wallet")
    x_nombreprovincia_id = fields.Char(string="Código Región",related='state_id.name')
    x_codigopais_id = fields.Char(string="Código País",related='country_id.code')
    x_inversor = fields.Boolean(string="Es Inversor",default=False)
    x_dni_front = fields.Binary(string='DNI Anverso')
    x_name_dni_front = fields.Char('Nombre Archivo')
    x_dni_back = fields.Binary(string='DNI Reverso')
    x_name_dni_back = fields.Char ('Nombre Archivo')
    x_dni_preview = fields.Binary('Vista Previa',compute='_get_preview')

    @api.depends('x_dni_front')
    def _get_preview(self):
        self.x_dni_preview = self.x_dni_front

    @api.multi
    def _kyc_docs(self):

        file = base64.decodestring(self.x_dni_front)
        extension = os.path.splitext(self.x_name_dni_front)[1]
        fobj = tempfile.NamedTemporaryFile(delete=False,suffix=extension)
        fname = fobj.name
        fobj.write(file)
        fobj.close()

        user_id = self.x_marketpayuser_id
        document = "USER_IDENTITY_PROOF"
        apikyc = swagger_client.KycApi()

        try:
            # Uploads a new document and uploads a file. If the document already exists it will be replaced.
            api_response = apikyc.kyc_post_document(document,fname,user_id)
            os.unlink(fname)


        except ApiException as e:
            raise osv.except_osv(('DNI'),
                                 ('Error al sincronizar el DNI por favor '
                                  'intentelo de nuevo más tarde'))
            print("Exception when calling KycApi->kyc_post_document: %s\n" % e)

        file = base64.decodestring(self.x_dni_back)
        extension = os.path.splitext(self.x_name_dni_back)[1]
        fobj = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
        fname = fobj.name
        fobj.write(file)
        fobj.close()

        try:
            # Uploads a new document and uploads a file. If the document already exists it will be replaced.
            api_response = apikyc.kyc_post_document(document,fname,user_id)
            os.unlink(fname)

        except ApiException as e:
            raise osv.except_osv(('DNI'),
                                 ('Error al sincronizar el DNI por favor '
                                  'intentelo de nuevo más tarde'))
            print("Exception when calling KycApi->kyc_post_document: %s\n" % e)

        return

    @api.multi
    def _kyc_validation(self):

        # create an instance of the API class
        user_id = self.x_marketpayuser_id # int | The Id of a user
        apikyc = swagger_client.KycApi()
        address = swagger_client.Address(address_line1=self.street,
                                         address_line2=self.street2,
                                         city=self.city, postal_code=self.zip,
                                         country=self.x_codigopais_id,
                                         region=self.x_nombreprovincia_id)

        kyc_user_natural = swagger_client.KycUserNaturalPut(address=address)
        kyc_user_natural.email = self.email
        kyc_user_natural.first_name = self.name
        kyc_user_natural.occupation = self.function
        kyc_user_natural.tag = self.comment
        kyc_user_natural.country_of_residence = self.x_codigopais_id
        kyc_user_natural.nationality = self.x_codigopais_id
        kyc_user_natural.id_card = self.vat

        try:
            # Update a Natural User Kyc Data
            api_response = apikyc.kyc_post_natural(user_id,
                                                   kyc_user_natural=kyc_user_natural)
            self.x_inversor = True
        except ApiException as e:
            raise osv.except_osv(('KyC'),
                                 ('Error al validar Usuario por favor '
                                  'intentelo de nuevo más tarde'))
            print("Exception when calling KycApi->kyc_post_natural: %s\n" % e)

        return

    @api.multi
    def _get_id(self):

        ############# Function Create User on MarketPay #####################
        apiUser = swagger_client.UsersApi()
        address = swagger_client.Address(address_line1=self.street, address_line2=self.street2,
                                         city=self.city, postal_code=self.zip,
                                         country=self.x_codigopais_id, region=self.x_nombreprovincia_id)
        user_natural = swagger_client.UserNaturalPost(address=address)
        user_natural.email = self.email
        user_natural.first_name = self.name
        user_natural.occupation = self.function
        user_natural.tag = self.comment
        user_natural.country_of_residence = self.x_codigopais_id
        user_natural.nationality = self.x_codigopais_id
        user_natural.id_card = self.vat

        try:
            api_response = apiUser.users_post_natural(user_natural=user_natural)
            self.x_marketpayuser_id = api_response.id

        except ApiException as e:
            raise osv.except_osv(('Marketpay ID'),
                                 ('Error al Registrar Usuario por favor '
                                  'intentelo de nuevo más tarde'))
            print("Exception when calling UsersApi->users_post: %s\n" % e)

        return

    @api.multi
    def _get_wallet(self):

        ###########Create wallet for the user########################
        apiWallet = swagger_client.WalletsApi()
        ownersList = [self.x_marketpayuser_id]
        wallet = swagger_client.WalletPost(owners=ownersList,
                                           description="wallet en EUR",
                                           currency='EUR')

        try:
            api_response = apiWallet.wallets_post(wallet=wallet)
            self.x_marketpaywallet_id = api_response.id

        except ApiException as e:
            raise osv.except_osv(('Marketpay Wallet'),
                                 ('Error al Registrar Wallet por favor '
                                  'intentelo de nuevo más tarde'))
            print("Exception when calling WalletApi->Wallet_post: %s\n" % e)

        return

    @api.multi
    def _updateuser(self):
        if self.name != False:
            if self.x_marketpayuser_id != False:
                # Marketpay Vars

                marketpay_key = "73a4d867-aeec-4e89-a295-64f14dc25ab9"
                marketpay_secret = "kFNm3CQU-ynHaM5g4OZ4MsSxOqmM85j4lgOVLkCgQYY="
                marketpay_domain = "https://api-sandbox.marketpay.io"

                # Swagger conf

                token_url = 'https://api-sandbox.marketpay.io/v2.01/oauth/token'
                key = 'Basic %s' % base64.b64encode(
                    b'73a4d867-aeec-4e89-a295-64f14dc25ab9:kFNm3CQU-ynHaM5g4OZ4MsSxOqmM85j4lgOVLkCgQYY=').decode(
                    'ascii')
                data = {'grant_type': 'client_credentials'}
                headers = {'Authorization': key,
                           'Content-Type': 'application/x-www-form-urlencoded'}

                r = requests.post(token_url, data=data, headers=headers)

                rs = r.content.decode()
                response = json.loads(rs)
                token = response['access_token']

                # Default for Swagger
                config = swagger_client.Configuration()
                config.host = marketpay_domain
                config.access_token = token
                client = swagger_client.ApiClient(configuration=config)
                api_instance = swagger_client.Configuration.set_default(config)

                apiUser = swagger_client.UsersApi()
                print(self.x_codigopais_id)
                address = swagger_client.Address(address_line1=self.street,
                                                 address_line2=self.street2,
                                                 city=self.city,
                                                 postal_code=self.zip,
                                                 country=self.x_codigopais_id,
                                                 region=self.x_nombreprovincia_id)

                user_id = self.x_marketpayuser_id
                user_natural = swagger_client.UserNaturalPut(address=address)
                user_natural.email = self.email
                user_natural.first_name = self.name
                user_natural.occupation = self.function
                user_natural.tag = self.comment
                user_natural.country_of_residence = self.x_codigopais_id
                user_natural.nationality = self.x_codigopais_id

                try:

                    api_response = apiUser.users_put_natural(user_id,
                                                             user_natural=user_natural)

                except ApiException as e:
                    print(
                        "Exception when calling UsersApi->users_put: %s\n" % e)

    @api.multi
    def marketpay_validate(self):

        if self.name == False:
            raise osv.except_osv(('Nombre'),
                                 ('El campo Nombre es obligatorio'))
        if self.country_id == False:
            raise osv.except_osv(('x_codigopais_id'),
                                 ('El campo pais es obligatorio'))
        if self.state_id == False:
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
        if self.vat == False:
            raise osv.except_osv(('vat'),
                                 ('El campo vat es obligatorio'))
        if self.x_dni_front == None:
            raise osv.except_osv(('DNI'),
                                 ('El campo DNI Anverso es obligatorio'))
        if self.x_dni_back == None:
            raise osv.except_osv(('DNI'),
                                 ('El campo DNI Reverso es obligatorio'))

        # Marketpay Vars
        marketpay_key = "73a4d867-aeec-4e89-a295-64f14dc25ab9"
        marketpay_secret = "kFNm3CQU-ynHaM5g4OZ4MsSxOqmM85j4lgOVLkCgQYY="
        marketpay_domain = "https://api-sandbox.marketpay.io"
        # Get Token
        token_url = 'https://api-sandbox.marketpay.io/v2.01/oauth/token'
        key = 'Basic %s' % base64.b64encode(
            b'73a4d867-aeec-4e89-a295-64f14dc25ab9:kFNm3CQU-ynHaM5g4OZ4MsSxOqmM85j4lgOVLkCgQYY=').decode(
            'ascii')
        data = {'grant_type': 'client_credentials'}
        headers = {'Authorization': key,
                   'Content-Type': 'application/x-www-form-urlencoded'}

        r = requests.post(token_url, data=data, headers=headers)

        rs = r.content.decode()
        response = json.loads(rs)
        token = response['access_token']

        # Load Default Config for Swagger
        config = swagger_client.Configuration()
        config.host = marketpay_domain
        config.access_token = token
        client = swagger_client.ApiClient(configuration=config)
        api_instance = swagger_client.Configuration.set_default(config)

        #if self.x_marketpayuser_id != False:
        # self._updateuser()
        if self.x_marketpayuser_id == False:
            self._get_id()
        if self.x_marketpaywallet_id == False:
            self._get_wallet()
        if self.x_inversor == False:
            self._kyc_validation()
            self._kyc_docs()
        else:
            self._updateuser()

