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


class ShareHolder(models.Model):
    _inherit = 'res.partner'

    share_percentage = fields.Float(
        string="Share percentage",
    )
    shareholder_id = fields.Char(
        string="Shareholder Id",
    )
    is_shareholder = fields.Boolean(
        string="Is Share Holder",
    )
    is_legal_representative = fields.Boolean(
        string="Is Legal Rep",
    )
    legal_representative_id = fields.Char(
        string="Legal Rep",
    )
    fiscal_doc = fields.Binary(
        string="Fiscal ID",
    )
    fiscal_doc_name = fields.Char(
        string="Fiscal ID",
    )
    registration_proof = fields.Binary(
        string="Registration Proof",
    )
    registration_proof_name = fields.Char()
    tax_register_declaration = fields.Binary(
        string="Tax Register Declaration",
    )
    tax_register_declaration_name = fields.Char()
    shareholder_declaration = fields.Binary(
        string="Shareholder Declaration",
    )
    shareholder_declaration_name = fields.Char()
    share_capital_increase = fields.Binary(
        string="Share Capital",
    )
    share_capital_increase_name = fields.Char()
    power_of_attorney = fields.Binary(
        string="Power of Attorney",
    )
    power_of_attorney_name = fields.Char()

    @api.multi
    def _add_shareholder(self):
        self.env.user.company_id._set_swagger_config()
        user_id = self.env.user.company_id.marketpayuser_id

        apikyc = swagger_client.KycApi()
        address = swagger_client.Address(address_line1=self.street,
                                         address_line2=self.street2,
                                         city=self.city, postal_code=self.zip,
                                         country=self.x_codigopais_id,
                                         region=self.x_nombreprovincia_id)
        telephone = swagger_client.Telephone(country_code=self.x_codigopais_id,
                                             number=self.phone,
                                             )

        share_holder_natural = swagger_client.KycUserValidationShareHolderNaturalPost(
            email=self.email,
            first_name=self.name,
            country_of_residence=self.x_codigopais_id,
            nationality=self.x_codigopais_id,
            id_card=self.vat,
            share_percentage=self.share_percentage,
            address=address,
            telephone=telephone,
        )

        try:
            api_response = apikyc.kyc_post_legal_share_holder(user_id, share_holder_natural=share_holder_natural)
            self.shareholder_id = api_response.id
            self.validated_by = self.env.user.name
        except ApiException as e:
            print(e)
            raise Warning(("MarketPay connection error: %s\n" % e))

    @api.multi
    def _kyc_shareholder_docs(self):

        user_id = self.parent_id.x_marketpayuser_id
        file = base64.decodebytes(self.fiscal_doc)
        extension = os.path.splitext(self.fiscal_doc_name)[1]
        fobj = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
        fname = fobj.name
        fobj.write(file)
        fobj.close()
        document = "USER_IDENTITY_PROOF"
        apikyc = swagger_client.KycApi()

        try:

            api_response = apikyc.kyc_post_document_shareholder(
                document_type=document,
                file=fname,
                shareholder_id=self.shareholder_id,
                user_id=user_id)

            os.unlink(fname)
        except ApiException as e:
            print(e)
            raise Warning(("MarketPay connection error: %s\n" % e))

    @api.multi
    def _add_boardmember(self):
        self.env.user.company_id._set_swagger_config()
        user_id = self.env.user.company_id.marketpayuser_id
        if not self.legal_representative_id:
            apikyc = swagger_client.KycApi()
            address = swagger_client.Address(address_line1=self.street,
                                             address_line2=self.street2,
                                             city=self.city, postal_code=self.zip,
                                             country=self.x_codigopais_id,
                                             region=self.x_nombreprovincia_id)
            telephone = swagger_client.Telephone(country_code=self.x_codigopais_id,
                                                 number=self.phone,
                                                 )

            board_member = swagger_client.KycUserValidationBoardMemberPost(address=address, telephone=telephone)
            board_member.email = self.email
            board_member.first_name = self.name
            board_member.country_of_residence = self.x_codigopais_id
            board_member.nationality = self.x_codigopais_id
            board_member.id_card = self.vat
            board_member.share_percentage = self.share_percentage
            try:
                api_response = apikyc.kyc_post_legal_board_member(
                    self.parent_id.x_marketpayuser_id, board_member=board_member
                )
                self.legal_representative_id = api_response.id
                self.validated_by = self.env.user.name
            except ApiException as e:
                print(e)
                raise Warning(("MarketPay connection error: %s\n" % e))

    @api.multi
    def _kyc_boardmember_docs(self, doc, doc_name, doc_type):
        file = base64.decodebytes(doc)
        extension = os.path.splitext(doc_name)[1]
        fobj = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
        fname = fobj.name
        fobj.write(file)
        fobj.close()
        apikyc = swagger_client.KycApi()
        try:
            api_response = apikyc.kyc_post_document_board_member(self.legal_representative_id, doc_type, fname,
                                                                 self.parent_id.x_marketpayuser_id)
            os.unlink(fname)
        except ApiException as e:
            print(e)
            raise Warning(("MarketPay connection error: %s\n" % e))

    @api.multi
    def shareholder_or_legal_validate(self):
        self.ensure_one()
        if not self.parent_id.x_marketpayuser_id:
            raise ValidationError(_('El Usuario debe pertenecer a una compañía dada de alta en MarketPay'))
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
        if not self.phone:
            raise ValidationError(_('Field phone is mandatory'))
        if not self.fiscal_doc:
            raise ValidationError(_('Field Identity Document is mandatory'))
        if self.is_shareholder:
            if not self.share_percentage:
                raise ValidationError(_('Field share percentage is empty'))

        self.env.user.company_id._set_swagger_config()

        if self.is_shareholder:
            if not self.shareholder_id:
                self._add_shareholder()
            self._kyc_shareholder_docs()
        if self.is_legal_representative:
            if not self.legal_representative_id:
                self._add_boardmember()
                if self.fiscal_doc:
                    doc_type = "USER_IDENTITY_PROOF"
                    self._kyc_boardmember_docs(self.fiscal_doc, self.fiscal_doc_name, doc_type)
                if self.power_of_attorney:
                    doc_type = "POWER_OF_ATTORNEY"
                    self._kyc_boardmember_docs(self.power_of_attorney, self.power_of_attorney_name, doc_type)


