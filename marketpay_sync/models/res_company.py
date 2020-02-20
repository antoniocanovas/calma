from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning

import tempfile
import os
import requests
import base64
import json
import logging
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


class ResCompany(models.Model):
    _inherit = 'res.company'

    marketpayuser_id = fields.Char(
        string="Marketpay ID",
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
    marketpay_key = fields.Char(
        string="Key",
    )
    marketpay_secret = fields.Char(
        string="secret",
    )
    marketpay_domain = fields.Char(
        default='https://api-sandbox.marketpay.io',
    )
    token_url = fields.Char(
        default='https://api-sandbox.marketpay.io/v2.01/oauth/token',
    )

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
    def _kyc_legal_validation(self):
        self.ensure_one()
        user_id = self.marketpayuser_id  # int | The Id of a user
        apikyc = swagger_client.KycApi()
        address = swagger_client.Address(address_line1=self.street,
                                         address_line2=self.street2,
                                         city=self.city, postal_code=self.zip,
                                         country=self.x_codigopais_id,
                                         region=self.x_nombreprovincia_id)

        kyc_user_legal = swagger_client.KycUserLegalPut(fiscal_address=address)
        kyc_user_legal.email = self.email
        kyc_user_legal.name = self.name
        kyc_user_legal.legal_representative_country_of_residence = self.x_codigopais_id
        kyc_user_legal.legal_representative_nationality = self.x_codigopais_id
        kyc_user_legal.fiscal_id = self.vat
        try:
            api_response = apikyc.kyc_post_legal(user_id, kyc_user_legal=kyc_user_legal)
        except ApiException as e:
            print(e)
            raise Warning(("MarketPay connection error: %s\n" % e))

    @api.multi
    def get_marketpay_id(self):
        self._marketpay_validate()
        self._set_swagger_config()
        if not self.marketpayuser_id:
            apiUser = swagger_client.UsersApi()
            address = swagger_client.Address(
                address_line1=self.street,
                address_line2=self.street2,
                city=self.city,
                postal_code=self.zip,
                country=self.x_codigopais_id,
                region=self.x_nombreprovincia_id,
            )

            user_legal = swagger_client.UserLegalPost(headquarters_address=address)
            user_legal.legal_representative_email = self.email
            user_legal.email = self.email
            user_legal.name = self.name
            user_legal.legal_representative_country_of_residence = self.x_codigopais_id
            user_legal.legal_representative_nationality = self.x_codigopais_id
            user_legal.legal_person_type = "BUSINESS"

            try:
                api_response = apiUser.users_post_legal(
                    user_legal=user_legal)
                self.marketpayuser_id = api_response.id
                self.partner_id.x_marketpayuser_id = api_response.id
                self.partner_id.x_inversor = True
                self.partner_id.validated_by = self.env.user.name
            except ApiException as e:
                print(e)
                raise Warning(("MarketPay connection error: %s\n" % e))

            self._kyc_legal_validation()

        else:
            self._kyc_legal_validation()

    @api.multi
    def _marketpay_validate(self):
        if not self.x_codigopais_id:
            raise ValidationError(_('El campo pais es obligatorio'))
        if not self.x_nombreprovincia_id:
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
            raise ValidationError(_('El Cif es obligatorio'))



