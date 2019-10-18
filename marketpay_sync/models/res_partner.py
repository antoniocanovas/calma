from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from swagger_client.rest import ApiException
import tempfile
import os
import requests
import base64
import json
import swagger_client


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_marketpayuser_id = fields.Char(
        string="Marketpay User",
    )
    x_marketpaywallet_id = fields.Char(
        string="Marketpay Wallet",
    )
    x_nombreprovincia_id = fields.Char(
        string="Código Región",
        related='state_id.name',
        readonly=True,
    )
    x_codigopais_id = fields.Char(
        string="Código País",
        related='country_id.code',
        readonly=True,
    )
    x_inversor = fields.Boolean(
        string="Es Inversor",
    )
    x_dni_front = fields.Binary(
        string='DNI Anverso',
    )
    x_name_dni_front = fields.Char(
        string='Nombre Archivo',
    )
    x_dni_back = fields.Binary(
        string='DNI Reverso',
    )
    x_name_dni_back = fields.Char(
        string='Nombre Archivo',
    )
    x_dni_f_preview = fields.Binary(
        string='Vista Previa',
        compute='_compute_image_f',
    )
    x_dni_b_preview = fields.Binary(
        string='Vista previa',
        compute='_compute_image_b',
    )

    @api.depends('x_dni_front')
    def _compute_image_f(self):
        for record in self:
            record.x_dni_f_preview = record.x_dni_front

    @api.depends('x_dni_back')
    def _compute_image_b(self):
        for record in self:
            record.x_dni_b_preview = record.x_dni_back

    @api.multi
    def _kyc_docs(self):
        file = base64.decodebytes(self.x_dni_front)
        extension = os.path.splitext(self.x_name_dni_front)[1]
        fobj = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
        fname = fobj.name
        fobj.write(file)
        fobj.close()
        user_id = self.x_marketpayuser_id
        document = "USER_IDENTITY_PROOF"
        apikyc = swagger_client.KycApi()
        try:
            apikyc.kyc_post_document(document, fname, user_id)
            os.unlink(fname)
        except ApiException as e:
            raise ValidationError(
                _('Error al sincronizar el DNI. Por favor intentelo de nuevo '
                  'más tarde'))
        file = base64.decodebytes(self.x_dni_back)
        extension = os.path.splitext(self.x_name_dni_back)[1]
        fobj = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
        fname = fobj.name
        fobj.write(file)
        fobj.close()
        try:
            apikyc.kyc_post_document(document, fname, user_id)
            os.unlink(fname)
        except ApiException as e:
            raise ValidationError(
                _('Error al sincronizar el DNI, por favor intentelo de nuevo '
                  'más tarde'))

    @api.multi
    def _kyc_validation(self):
        self.ensure_one()
        user_id = self.x_marketpayuser_id  # int | The Id of a user
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
            apikyc.kyc_post_natural(user_id, kyc_user_natural=kyc_user_natural)
            self.x_inversor = True
        except ApiException as e:
            raise ValidationError(
                _('Error al validar Usuario, por favor intentelo de nuevo más '
                  'tarde'))

    @api.multi
    def _get_id(self):
        self.ensure_one()
        apiUser = swagger_client.UsersApi()
        address = swagger_client.Address(
            address_line1=self.street,
            address_line2=self.street2,
            city=self.city,
            postal_code=self.zip,
            country=self.x_codigopais_id,
            region=self.x_nombreprovincia_id)
        user_natural = swagger_client.UserNaturalPost(address=address)
        user_natural.email = self.email
        user_natural.first_name = self.name
        user_natural.occupation = self.function
        user_natural.tag = self.comment
        user_natural.country_of_residence = self.x_codigopais_id
        user_natural.nationality = self.x_codigopais_id
        user_natural.id_card = self.vat
        try:
            api_response = apiUser.users_post_natural(
                user_natural=user_natural)
            self.x_marketpayuser_id = api_response.id
        except ApiException as e:
            raise ValidationError(
                _('Error al Registrar Usuario, por favor intentelo de nuevo '
                  'más tarde'))

    @api.multi
    def _get_wallet(self):
        self.ensure_one()
        apiWallet = swagger_client.WalletsApi()
        ownersList = [self.x_marketpayuser_id]
        wallet = swagger_client.WalletPost(owners=ownersList,
                                           description="wallet en EUR",
                                           currency='EUR')
        try:
            api_response = apiWallet.wallets_post(wallet=wallet)
            self.x_marketpaywallet_id = api_response.id
        except ApiException as e:
            raise ValidationError(
                _('Error al Registrar Wallet, por favor intentelo de nuevo '
                  'más tarde'))

    @api.multi
    def _updateuser(self):
        self.ensure_one()
        if self.name and self.x_marketpayuser_id:
            marketpay_domain = self.company_id.marketpay_domain
            token_url = self.company_id.token_url
            key = self.company_id._prepare_marketpay_key()
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
                apiUser.users_put_natural(user_id, user_natural=user_natural)
            except ApiException as e:
                print("Exception when calling UsersApi->users_put: %s\n" % e)

    @api.multi
    def marketpay_validate(self):
        self.ensure_one()
        if not self.name:
            raise ValidationError(_('El campo Nombre es obligatorio'))
        if not self.country_id:
            raise ValidationError(_('El campo pais es obligatorio'))
        if not self.state_id:
            raise ValidationError(_('El campo provincia es obligatorio'))
        if not self.email:
            raise ValidationError(_('El campo mail es obligatorio'))
        if not self.city:
            raise ValidationError(_('El campo ciudad es obligatorio'))
        if not self.street:
            raise ValidationError(_('El campo calle es obligatorio'))
        if not self.zip:
            raise ValidationError(_('El campo C.P es obligatorio'))
        if not self.vat:
            raise ValidationError(_('El campo vat es obligatorio'))
        if not self.x_dni_front:
            raise ValidationError(_('El campo DNI Anverso es obligatorio'))
        if not self.x_dni_back:
            raise ValidationError(_('El campo DNI Reverso es obligatorio'))
        marketpay_domain = self.company_id.marketpay_domain
        token_url = self.company_id.token_url
        key = self.company_id._prepare_marketpay_key()
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
        swagger_client.ApiClient(configuration=config)
        swagger_client.Configuration.set_default(config)

        if not self.x_marketpayuser_id:
            self._get_id()
        if not self.x_marketpaywallet_id:
            self._get_wallet()
        if not self.x_inversor:
            self._kyc_validation()
            self._kyc_docs()
        else:
            self._updateuser()
