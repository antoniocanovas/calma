import logging
import time
import requests
import re
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(
        selection_add=[
            ('payflow_pro', 'Cardit / Debit Card'),
        ],
    )
    payflow_partner = fields.Char(
        string='Partner ID',
        required_if_provider='payflow_pro',
        help='The ID provided to you by the authorized PayPal Reseller who '
             'registered you for the gateway. If you purchased your account '
             'directly from PayPal, use PayPal.',
    )
    payflow_vendor = fields.Char(
        string='Vender/Merchant ID',
        required_if_provider='payflow_pro',
        help='Your merchant login ID that you created when you registered for '
             'the account. ',
    )
    payflow_username = fields.Char(
        string='Username',
        required_if_provider='payflow_pro',
        help='If you set up one or more additional users on the account, this'
             ' value is the ID of the user authorized to process '
             'transactions.',
    )
    payflow_password = fields.Char(
        string='Password',
        required_if_provider='payflow_pro',
        help='The password that you defined while registering for the '
             'account.',
    )

    def _get_payflow_pro_urls(self):
        """ Payflow pro URLS """
        if self.environment == 'prod':
            return {'payflow_pro_url': 'https://payflowpro.paypal.com'}
        else:
            return {'payflow_pro_url': 'https://pilot-payflowpro.paypal.com'}

    @api.model
    def payflow_pro_s2s_form_process(self, data):
        values = {
            'cc_number': data.get('cc_number'),
            'cc_holder_name': data.get('cc_holder_name'),
            'cc_expiry': data.get('cc_expiry'),
            'cc_cvv': data.get('cc_cvv'),
            'cc_brand': data.get('cc_brand'),
            'acquirer_id': int(data.get('acquirer_id')),
            'partner_id': int(data.get('partner_id'))
        }
        PaymentMethod = self.env['payment.token'].sudo().create(values)
        return PaymentMethod

    @api.multi
    def payflow_pro_s2s_form_validate(self, data):
        error = dict()
        mandatory_fields = [
            "cc_number", "cc_cvv", "cc_holder_name", "cc_expiry", "cc_brand"]
        # Validation
        for field_name in mandatory_fields:
            if not data.get(field_name):
                error[field_name] = 'missing'
        return False if error else True

    @api.multi
    def payflow_pro_compute_fees(self, amount, currency_id, country_id):
        if not self.fees_active:
            return 0.0
        country = self.env['res.country'].browse(country_id)
        if country and self.company_id.country_id.id == country.id:
            percentage = self.fees_dom_var
            fixed = self.fees_dom_fixed
        else:
            percentage = self.fees_int_var
            fixed = self.fees_int_fixed
        fees = (percentage / 100.0 * amount + fixed) / (1 - percentage / 100.0)
        return fees

    @api.multi
    def payflow_pro_form_generate_values(self, partner_values):
        bill_information = dict(partner_values)
        if partner_values['partner']['parent_id']:
            ship_information = {
                'ship_to_same_as_bill': False,
                'ship_to_first_name': partner_values.get('first_name'),
                'ship_to_last_name': partner_values.get('last_name'),
                'ship_to_address1': partner_values.get('address'),
                'ship_to_city': partner_values.get('city'),
                'ship_to_state':
                    partner_values.get('state') and
                    partner_values['state'].code,
                'ship_to_zip': partner_values.get('zip'),
                'ship_to_country':
                    partner_values.get('country') and
                    partner_values.get('country').code,
                'ship_to_email': partner_values.get('email'),
                'ship_to_phone': partner_values.get('phone'),
            }
            bill_vals = partner_values['partner']['parent_id']
            bill_information.update(ship_information)
            bill_information.update({
                'currency_code':
                    partner_values.get('currency') and
                    partner_values.get('currency').name,
                'bill_to_first_name':
                    self._split_partner_name(bill_vals.name)[0],
                'bill_to_last_name':
                    self._split_partner_name(bill_vals.name)[1],
                'bill_to_address1': bill_vals.street,
                'bill_to_city': bill_vals.city,
                'bill_to_state': bill_vals.state_id.code or '',
                'bill_to_zip': bill_vals.zip or '',
                'bill_to_country': bill_vals.country_id.code,
                'bill_to_email': bill_vals.email or '',
                'bill_to_phone': bill_vals.phone,
            })
        else:
            bill_information.update({
                'ship_to_same_as_bill': True,
                'currency_code':
                    partner_values.get('currency') and
                    partner_values.get('currency').name,
                'bill_to_first_name': partner_values.get('first_name'),
                'bill_to_last_name': partner_values.get('last_name'),
                'bill_to_address1': partner_values.get('address'),
                'bill_to_city': partner_values.get('city'),
                'bill_to_state':
                    partner_values.get('state') and
                    partner_values['state'].code,
                'bill_to_zip': partner_values.get('zip'),
                'bill_to_country':
                    partner_values.get('country') and
                    partner_values.get('country').code,
                'bill_to_email': partner_values.get('email'),
                'bill_to_phone': partner_values.get('phone'),
            })
        payflow_tx_values = dict(bill_information)
        if self.fees_active:
            payflow_tx_values['handling'] = '%.2f' % payflow_tx_values.pop(
                'fees', 0.0)
        return payflow_tx_values

    @api.multi
    def payflow_pro_get_form_action_url(self):
        self.ensure_one()
        """ Override tx_url divert to Payflow Pro feedback controller """
        return '/payment/%s/s2s/feedback' % self.provider

    def _split_partner_name(self, partner_name):
        return [' '.join(partner_name.split()[-1:]), ' '.join(
            partner_name.split()[:-1])]

    def _build_parmlist(self, parmdict):
        """
        Converts a dictionary of name and value pairs into a PARAMETER LIST
        Payflow Pro accept only string value.
        """
        args = []
        for key, value in parmdict.items():
            if not (value is None):
                if isinstance(value, str):
                    key = '%s[%d]' % (key.upper(), len(value.encode('utf-8')))
                else:
                    key = '%s[%d]' % (key.upper(), len(str(value)))
                args.append('%s=%s' % (key, value))
        args.sort()
        parmlist = '&'.join(args)
        return parmlist

    def _build_dictlist(self, parmlist):
        """
        Parses a PARMLIST string into a dictionary of name and value
        pairs. The parsing is complicated by the following:
        """
        parmlist = "&" + parmlist
        name_re = re.compile(r'\&([A-Z0-9_]+)(\[\d+\])?=')

        results = {}
        offset = 0
        match = name_re.search(parmlist, offset)
        while match:
            name, len_suffix = match.groups()
            offset = match.end()
            if len_suffix:
                val_len = int(len_suffix[1:-1])
            else:
                next_match = name_re.search(parmlist, offset)
                if next_match:
                    val_len = next_match.start() - match.end()
                else:
                    val_len = len(parmlist) - match.end()
            value = parmlist[match.end(): match.end() + val_len]
            results[name.lower()] = value

            match = name_re.search(parmlist, offset)
        return results


class PaymentToken(models.Model):
    _inherit = 'payment.token'

    cc_number = fields.Char(
        string='Card Number',
    )
    cc_holder_name = fields.Char(
        string='Card Holder Name',
    )
    cc_expiry = fields.Char(
        string='Card Expiry',
    )
    cc_cvv = fields.Integer(
        string='CVV Code',
    )
    cc_brand = fields.Char(
        string='Card Brand',
    )

    @api.model
    def payflow_pro_create(self, values):
        """ Save Credit Card before account verify with TRXTYPE=A

        Account Verification, also known as zero dollar Authorization (
            TRXTYPE=A),
        verifies credit card information.
        - AMT: value is always 0 for varification.
        - RESULT: Although the RESULT values returned is 0 (Approved).
        - RESPMSG: The RESPMSG values returned Verified or Approved.

        """
        if values.get('cc_number'):
            Acquirer = self.env['payment.acquirer'].browse(
                values['acquirer_id'])
            values['cc_number'] = values['cc_number'].replace(' ', '')
            expiry = str(values['cc_expiry'][:2]) + str(
                values['cc_expiry'][-2:])
            cvv = values['cc_cvv'][:3]
            alias = 'ODOO-NEW-ALIAS-%s' % time.time()
            # Generate unique token (Current time in milliseconds)
            client_token_id = str(int(time.time() * 1000))
            req_param = {
                'partner': Acquirer.payflow_partner,
                'vendor': Acquirer.payflow_vendor,
                'user': Acquirer.payflow_username,
                'pwd': Acquirer.payflow_password,
                'trxtype': 'A',
                'tender': 'C',
                'createsecuretoken': 'Y',
                'securetokenid': client_token_id,
                'verbosity': 'HIGH',
                'AMT': 0,
                'ACCT': values['cc_number'],
                'expdate': expiry,
                'cvv': cvv,
            }
            parmlist = Acquirer._build_parmlist(req_param)
            payflow_pro_url = \
                Acquirer._get_payflow_pro_urls()['payflow_pro_url']
            headers = {
                'content-type': "application/x-www-form-urlencoded",
            }
            response = requests.request("POST", payflow_pro_url, data=parmlist,
                                        headers=headers)
            result_dictlist = Acquirer._build_dictlist(response.text)
            response.close()
            if not result_dictlist['result'] == '0':
                error = 'Payflow Pro get credit card authentication has ' \
                        'been failed'
                _logger.error(error)
                raise Exception(error)
            return {
                'acquirer_ref': alias,
                'name': 'XXXXXXXXXXXX%s - %s' % (values['cc_number'][-4:],
                                                 values['cc_holder_name'])
            }
        return {}


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    payflow_pnref = fields.Char(
        string='PNREF Number',
        help='The PNREF is a unique transaction identification number issued '
             'by PayPal that identifies the transaction for billing, '
             'reporting, and transaction data purposes.',
    )

    @api.multi
    def payflow_pro_s2s_do_transaction(self, vals):
        self.ensure_one()
        acquirer = self.acquirer_id
        pmethod = self.env['payment.token'].search([
            ('partner_id', '=', self.partner_id.id),
            ('acquirer_id', '=', acquirer.id),
        ], limit=1)
        if not pmethod:
            extra_payment_method = self.env['payment.token'].search([
                ('partner_id', '=', self.partner_id.id),
            ], order="id desc", limit=1)
            if not extra_payment_method:
                return False

        if pmethod:
            payment_method = pmethod
        else:
            payment_method = extra_payment_method

        payflow_credential = {
            'partner': acquirer.payflow_partner,
            'vendor': acquirer.payflow_vendor,
            'user': acquirer.payflow_username,
            'pwd': acquirer.payflow_password,
            'trxtype': 'S',
            'tender': 'C',
            'verbosity': 'HIGH'
        }
        req_params = dict(payflow_credential)
        req_params.update({
            'acct': payment_method.cc_number,
            'expdate': str(payment_method.cc_expiry[:2] +
                           payment_method.cc_expiry[-2:]),
            'cvv2': payment_method.cc_cvv,
            'orderid': vals.get('reference'),
            'amt': float(vals.get('amount')),
            'handlingamt': vals.get('handling'),
            'currency': vals.get('currency_code'),
            'billtofirstname': vals.get('bill_to_first_name'),
            'billtolastname': vals.get('bill_to_last_name'),
            'billtostreet': vals.get('bill_to_address1'),
            'billtocity': vals.get('bill_to_city'),
            'billtostate': vals.get('bill_to_state'),
            'billtozip': vals.get('bill_to_zip'),
            'billtocountry': vals.get('bill_to_city'),  # 840
            'billtoemail': vals.get('bill_to_email'),
            'billtophonenum': vals.get('bill_to_phone'),
            'shiptofirstname': vals.get('ship_to_first_name'),
            'shiptolastname': vals.get('ship_to_last_name'),
            'shiptostreet': vals.get('ship_to_address1'),
            'shiptocity': vals.get('ship_to_city'),
            'shiptostate': vals.get('ship_to_state'),
            'shiptozip': vals.get('ship_to_zip'),
            'shiptocountry': vals.get('ship_to_city'),  # 840
            'shiptoemail': vals.get('ship_to_email'),
            'shiptophonenum': vals.get('ship_to_phone'),
        })
        parmlist = acquirer._build_parmlist(req_params)
        payflow_pro_url = acquirer._get_payflow_pro_urls()['payflow_pro_url']
        try:
            headers = {
                'content-type': "application/x-www-form-urlencoded",
            }
            response = requests.request(
                "POST", payflow_pro_url, data=parmlist, headers=headers)
            result_dictlist = acquirer._build_dictlist(response.text)
            response.close()
        except Exception as e:
            _logger.exception(
                'Payflow Pro get CAPTURE request failed - %s', e)
            raise UserWarning("Payflow Pro get CAPTURE request failed.")
        return result_dictlist

    @api.multi
    def s2s_feedback(self, data, acquirer_name):
        invalid_parameters, tx, validate = None, None, None
        tx_find_method_name = '_%s_s2s_get_tx_from_data' % acquirer_name
        if hasattr(self, tx_find_method_name):
            tx = getattr(self, tx_find_method_name)(data)

        invalid_param_method_name = '_%s_s2s_get_invalid_parameters' % \
                                    acquirer_name
        if hasattr(self, invalid_param_method_name):
            invalid_parameters = getattr(tx, invalid_param_method_name)(data)

        if invalid_parameters:
            _error_message = '%s: incorrect tx data:\n' % acquirer_name
            for item in invalid_parameters:
                _error_message += '\t%s: received %s instead of %s\n' % (
                    item[0], item[1], item[2])
            _logger.error(_error_message)
            return False

        feedback_method_name = '_%s_s2s_validate' % acquirer_name
        if hasattr(self, feedback_method_name):
            validate = getattr(tx, feedback_method_name)(data)

        if validate and \
                tx and tx.state == 'done' and \
                tx.sale_order_ids and tx.sale_order_ids[0].state in \
                ['draft', 'sent']:
            tx.sale_order_ids[0].sudo().with_context(
                send_email=True).action_confirm()
        return True

    @api.model
    def _payflow_pro_s2s_get_tx_from_data(self, data):
        reference, pnref_number = data.get('orderid'), data.get('pnref')
        if not reference:
            error_msg = _(
                'Payflow Pro: received data with missing ORDERID (%s)') % (
                            reference)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        if not pnref_number:
            error_msg = _(
                'Payflow Pro: received data with missing PNREF (%s)') % (
                            pnref_number)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        txns = self.env['payment.transaction'].search(
            [('reference', '=', reference)])
        if not txns or len(txns) > 1:
            error_msg = 'Payflow Pro: received data for reference %s' % (
                reference)
            if not txns:
                error_msg += ': no order found'
            else:
                error_msg += ': multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return txns[0]

    @api.model
    def _payflow_pro_s2s_get_invalid_parameters(self, data):
        invalid_parameters = []
        # Check order number
        if data.get('orderid') != self.reference:
            invalid_parameters.append(
                ('orderid', data.get('orderid'), self.reference))

        # Check acquirer reference order number
        if self.acquirer_reference and data.get('orderid') != \
                self.acquirer_reference:
            invalid_parameters.append(('orderid', data.get('orderid'),
                                       self.acquirer_reference))
        return invalid_parameters

    @api.model
    def _payflow_pro_s2s_validate(self, data):
        response = data.get('respmsg')
        tx_vals = {
            'payflow_pnref': data.get('pnref'),
            'acquirer_reference': data.get('orderid')
        }

        if data.get('result') == '0':
            _logger.info('%s payflow pro payment for tx %s: set as done' %
                         (response, self.reference))
            tx_vals.update({
                'state': 'done',
                'date': data.get('transtime')
            })
            return self.write(tx_vals)
        else:
            error = 'Received unrecognized RESULT for PayFlow Pro ' \
                    'payment %s: %s, set as error' % (self.reference, response)
            _logger.info(error)
            tx_vals.update({
                'state': 'error',
                'state_message': error
            })
            return self.write(tx_vals)

    def _check_or_create_sale_tx(self, order, acquirer, payment_token=None,
                                 tx_type='form', add_tx_values=None,
                                 reset_draft=True):
        tx = self
        if not tx:
            tx = self.search([('reference', '=', order.name)], limit=1)

        if tx.state in ['error', 'cancel']:  # filter incorrect states
            tx = False
        if (tx and tx.acquirer_id != acquirer) or (
                tx and tx.sale_order_id != order):  # filter unmatching
            tx = False
        if tx and payment_token and tx.payment_token_id and \
                payment_token != tx.payment_token_id:  # new or distinct token
            tx = False

        # still draft tx, no more info -> rewrite on tx or create a new one
        # depending on parameter
        if tx and tx.state == 'draft':
            if reset_draft:
                tx.write(dict(
                    self.on_change_partner_id(order.partner_id.id).get(
                        'value', {}),
                    amount=order.amount_total,
                    type=tx_type)
                )
            else:
                tx = False
        remaining_amount = order.amount_total
        if order.wallet_txn_id:
            remaining_amount -= order.wallet_txn_id.amount
        if not tx:
            tx_values = {
                'acquirer_id': acquirer.id,
                'type': tx_type,
                'amount': remaining_amount,
                'currency_id': order.pricelist_id.currency_id.id,
                'partner_id': order.partner_id.id,
                'partner_country_id': order.partner_id.country_id.id,
                'reference': self.get_next_reference(order.name),
                'sale_order_id': order.id,
            }
            if add_tx_values:
                tx_values.update(add_tx_values)
            if payment_token and payment_token.sudo().partner_id == \
                    order.partner_id:
                tx_values['payment_token_id'] = payment_token.id

            tx = self.create(tx_values)

        # update quotation
        order.write({
            'payment_tx_id': tx.id,
        })

        return tx
