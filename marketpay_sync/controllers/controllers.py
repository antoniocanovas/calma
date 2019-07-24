from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal

import base64


class CustomPortalDetails(CustomerPortal):
    MANDATORY_BILLING_FIELDS = CustomerPortal.MANDATORY_BILLING_FIELDS + \
                              ["zipcode", "state_id", "vat",
                               "x_name_dni_front", "x_name_dni_back"]

    @route(['/my/account'], type='http', auth='user', website=True)
    def account(self, redirect=None, **post):
        dni_front = False
        dni_back = False
        if post:
            dni_front = post.pop('x_dni_front')
            dni_back = post.pop('x_dni_back')
        response = super(CustomPortalDetails, self).account(
            redirect=redirect, **post)
        if post:
            partner = request.env.user.partner_id
            partner.sudo().write({
                'x_dni_back': base64.encodebytes(dni_back.read()),
                'x_dni_front': base64.encodebytes(dni_front.read()),
                'x_name_dni_back': dni_back.filename,
                'x_name_dni_front': dni_front.filename,
            })
        return response
