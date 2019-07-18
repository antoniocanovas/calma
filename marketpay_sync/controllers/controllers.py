
from odoo.addons.portal.controllers.portal import CustomerPortal


class CustomPortalDetails(CustomerPortal):
    MANDATORY_BILLING_FIELDS = CustomerPortal.MANDATORY_BILLING_FIELDS + \
                              ["zipcode", "state_id", "vat",'x_dni_front',
                               'x_dni_back']