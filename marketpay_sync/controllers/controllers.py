from odoo import _
from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal

import base64


class CustomPortalDetails(CustomerPortal):
    MANDATORY_BILLING_FIELDS = CustomerPortal.MANDATORY_BILLING_FIELDS + \
                               ["zipcode", "state_id", "vat", "fiscal_doc",
                                "company_type"]

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
            dni_front = post.pop('fiscal_doc')

            error, error_message = self.details_form_validate(post)
            if error.get('fiscal_doc') and dni_front:
                error.pop('fiscal_doc')
                if not error:
                    error_message = []
            if error.get('fiscal_doc'):
                error_message.append(
                    _(' Please, upload an image for dni with both sides, and an '
                      'spanish national identity card is needed to invest.'))
            values.update({'error': error, 'error_message': error_message})
            values.update(post)
            if not error:
                post.update({
                    'fiscal_doc': base64.encodebytes(dni_front.read()),
                })
                values = {key: post[key] for key in
                          self.MANDATORY_BILLING_FIELDS}
                values.update(
                    {key: post[key] for key in self.OPTIONAL_BILLING_FIELDS if
                     key in post})
                values.update({'zip': values.pop('zipcode', ''),
                               'fiscal_doc_name': dni_front.filename,
                               })
                partner.sudo().write(values)
                if redirect:
                    return request.redirect(redirect)
                if not partner.x_inversor:
                    if partner.company_type == "person":
                        response = request.render("marketpay_sync.http_warning_signup", values)
                        response.headers['X-Frame-Options'] = 'DENY'
                        return response
                    else:
                        response = request.render("marketpay_sync.portal_company_docs_warning", values)
                        response.headers['X-Frame-Options'] = 'DENY'
                        return response
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
        response = request.render("marketpay_sync.portal_my_details_inh", values)
        return response

