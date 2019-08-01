from odoo import _
from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal

import base64


class CustomPortalDetails(CustomerPortal):
    MANDATORY_BILLING_FIELDS = CustomerPortal.MANDATORY_BILLING_FIELDS + \
                              ["zipcode", "state_id", "vat", "x_dni_front",
                               "x_dni_back"]

    @route(['/my/account'], type='http', auth='user', website=True)
    def account(self, redirect=None, **post):
        # Overwrite method to manage response better
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        values.update({
            'error': {},
            'error_message': [],
        })
        if post:
            dni_front = post.pop('x_dni_front')
            dni_back = post.pop('x_dni_back')
            print("DEBUG")
            print(dni_front.name)

            error, error_message = self.details_form_validate(post)
            if error.get('x_dni_front') and dni_front:
                error.pop('x_dni_front')
                if not error:
                    error_message = []
            if error.get('x_dni_back') and dni_back:
                error.pop('x_dni_back')
                if not error:
                    error_message = []
            if error.get('x_dni_front'):
                error_message.append(
                    _(' Please, upload an image for dni front field.'))
            if error.get('x_dni_back'):
                error_message.append(
                    _(' Please, upload an image for dni back field.'))
            values.update({'error': error, 'error_message': error_message})
            values.update(post)
            if not error:
                post.update({
                    'x_dni_back': base64.encodebytes(dni_back.read()),
                    'x_dni_front': base64.encodebytes(dni_front.read()),
                })
                values = {key: post[key] for key in
                          self.MANDATORY_BILLING_FIELDS}
                values.update(
                    {key: post[key] for key in self.OPTIONAL_BILLING_FIELDS if
                     key in post})
                values.update({'zip': values.pop('zipcode', ''),
                               'x_name_dni_back': dni_back.filename,
                               'x_name_dni_front': dni_front.filename,
                               })
                partner.sudo().write(values)
                if redirect:
                    return request.redirect(redirect)
                return request.redirect('/my/home')
        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([])
        values.update({
            'partner': partner,
            'countries': countries,
            'states': states,
            'has_check_vat': hasattr(request.env['res.partner'], 'check_vat'),
            'redirect': redirect,
            'page_name': 'my_details',
        })
        response = request.render("portal.portal_my_details", values)
        response.headers['X-Frame-Options'] = 'DENY'
        return response
