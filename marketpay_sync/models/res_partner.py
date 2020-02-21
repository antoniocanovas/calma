from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

import tempfile
import os
import base64
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
        string='Nombre Anverso',
    )
    x_dni_back = fields.Binary(
        string='DNI Reverso',
    )
    x_name_dni_back = fields.Char(
        string='Nombre Reverso',
    )
    x_dni_f_preview = fields.Binary(
        string='Vista Previa',
        compute='_compute_image_f',
    )
    x_dni_b_preview = fields.Binary(
        string='Vista previa',
        compute='_compute_image_b',
    )
    validated_by = fields.Char(
        string='Validado por',
    )
    investment_count = fields.Integer(
        compute='_compute_investment_count',
        string='Investment Count',
    )
    sale_order_line_ids = fields.One2many(
        comodel_name='sale.order.line',
        inverse_name='order_partner_id',
        string='Sales Order Lines',
    )

    def _get_sale_lines(self, domain):
        # To easy filter sale order lines
        sale_order_line = self.env['sale.order.line']
        domain += [('is_investment', '=', True)]
        return sale_order_line.search(domain)

    def _compute_investment_count(self):
        for partner in self:
            sale_lines = self._get_sale_lines(
                [('order_partner_id', 'in', partner.ids)])
            partner.investment_count = len(sale_lines.mapped('order_id'))

    @api.multi
    def action_view_sale_lines(self):
        sale_lines = self._get_sale_lines(
            [('order_partner_id', 'in', self.ids)])
        action = self.env.ref(
            'calma_grid.action_sales_order_line_calma').read()[0]
        action['domain'] = [('id', 'in', sale_lines.ids)]
        return action

    @api.depends('x_dni_front')
    def _compute_image_f(self):
        for record in self:
            record.x_dni_f_preview = record.x_dni_front

    @api.depends('x_dni_back')
    def _compute_image_b(self):
        for record in self:
            record.x_dni_b_preview = record.x_dni_back

    @api.multi
    def _kyc_legal_docs(self, doc, doc_name, doc_type):
        user_id = self.x_marketpayuser_id

        if doc:
            file = base64.decodebytes(doc)
            extension = os.path.splitext(doc_name)[1]
            fobj = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
            fname = fobj.name
            fobj.write(file)
            fobj.close()
            document = doc_type
            apikyc = swagger_client.KycApi()
            try:
                api_response = apikyc.kyc_post_document(document, fname, user_id)
                os.unlink(fname)
            except Exception as e:
                raise Warning(("MarketPay connection error: %s\n" % e))

    @api.multi
    def _kyc_put_docs(self, doc, doc_name, doc_type):
        user_id = self.x_marketpayuser_id

        if doc:
            file = base64.decodebytes(doc)
            extension = os.path.splitext(doc_name)[1]
            fobj = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
            fname = fobj.name
            fobj.write(file)
            fobj.close()
            document = doc_type
            apikyc = swagger_client.KycApi()
            try:
                api_response = apikyc.kyc_put_document(document, fname, user_id)
                os.unlink(fname)
            except Exception as e:
                raise Warning(("MarketPay connection error: %s\n" % e))

    @api.multi
    def prepare_kyc_docs(self):
        self.env.user.company_id._set_swagger_config()

        if self.x_dni_front:
            doc_type = "USER_IDENTITY_PROOF"
            self._kyc_legal_docs(self.x_dni_front, self.x_name_dni_front, doc_type)
        if self.x_dni_back:
            doc_type = "USER_IDENTITY_PROOF"
            self._kyc_put_docs(self.x_dni_back, self.x_name_dni_back, doc_type)
        if self.fiscal_doc:
            doc_type = "FISCAL_ID"
            self._kyc_legal_docs(self.fiscal_doc, self.fiscal_doc_name, doc_type)
        if self.registration_proof:
            doc_type = "REGISTRATION_PROOF"
            self._kyc_legal_docs(self.registration_proof, self.registration_proof_name, doc_type)
        if self.tax_register_declaration:
            doc_type = "ARTICLES_OF_ASSOCIATION"
            self._kyc_legal_docs(self.tax_register_declaration, self.tax_register_declaration_name, doc_type)
        if self.shareholder_declaration:
            doc_type = "SHAREHOLDER_DECLARATION"
            self._kyc_legal_docs(self.shareholder_declaration, self.shareholder_declaration_name, doc_type)
        if self.share_capital_increase:
            doc_type = "SHARE_CAPITAL_INCREASE"
            self._kyc_legal_docs(self.share_capital_increase, self.share_capital_increase_name, doc_type)


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
            self.validated_by = self.env.user.name
        except ApiException as e:
            raise ValidationError(
                _('Error al validar Usuario, por favor intentelo de nuevo más '
                  'tarde'))

    @api.multi
    def _kyc_legal_validation(self):
        self.ensure_one()
        user_id = self.x_marketpayuser_id  # int | The Id of a user
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
            self.x_inversor = True
            self.validated_by = self.env.user.name
        except ApiException as e:
            print(e)
            raise Warning(("MarketPay connection error: %s\n" % e))

    @api.multi
    def _get_legal_marketpay_id(self):

        if not self.x_marketpayuser_id:
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
                self.x_marketpayuser_id = api_response.id
            except ApiException as e:
                raise ValidationError(
                    _('Error al Registrar Usuario, por favor intentelo de nuevo '
                      'más tarde'))

            self._kyc_legal_validation()

        else:
            self._kyc_legal_validation()

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
            self.env.user.company_id._set_swagger_config()

            apiUser = swagger_client.UsersApi()
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
                print(e)
                raise Warning(("MarketPay connection error: %s\n" % e))

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
        if self.is_legal_representative or self.is_shareholder or self.company_type == 'company':
            if not self.fiscal_doc:
                raise ValidationError(_('Field Identity Document is mandatory'))
        if not self.is_legal_representative and not self.is_shareholder and not self.company_type == 'company':
            if not self.x_dni_front:
                raise ValidationError(_('Field Identity Document side A'))
            if not self.x_dni_back:
                raise ValidationError(_('Field Identity Document side B'))


        self.env.user.company_id._set_swagger_config()

        if not self.x_marketpayuser_id:
            if self.company_type != "company":
                self._get_id()
            else:
                self._get_legal_marketpay_id()
        if not self.x_marketpaywallet_id:
            self._get_wallet()
        if not self.x_inversor:
            if self.company_type != "company":
                self._kyc_validation()
            else:
                self._kyc_legal_validation()
            self.prepare_kyc_docs()
