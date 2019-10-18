import logging
import pprint
import werkzeug
import json
from datetime import datetime
import swagger_client
from swagger_client.rest import ApiException

from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class CalmaWebsiteWallet(http.Controller):
    @http.route(['/wallet/add/money'], type='http', auth="user", website=True)
    def wallet_add_money(self, **post):
        acquirers = request.env['payment.acquirer'].sudo().search([
            ('website_published', '=', True),
            ('is_wallet_acquirer', '=', True)])
        values = dict()
        values['form_acquirers'] = [acq for acq in acquirers if
                                    acq.payment_flow == 'form' and
                                    acq.view_template_id]
        values = {
            'wallet_bal': request.env.user.partner_id.wallet_balance,
            'acquirers': acquirers,
            'form_acquirers': values['form_acquirers'],
        }
        return request.render("website_wallet.add_money", values)

    @http.route(['/wallet/add/money/quantity'], type='http', auth="user",
                website=True)
    def wallet_add_money_txn(self, **post):
        user = request.env.user
        partner = user.partner_id
        PA = request.env['payment.acquirer'].sudo()
        PT = request.env['payment.transaction'].sudo()

        if post.get('amount') == '':
            return request.redirect("/wallet/add/money")

        if post.get('amount'):
            amount = float(post.get('amount')) > 0
            if not amount or not post.get('payment_acquirer'):
                return request.redirect("/wallet/add/money")

        add_amount = float(post.get('amount'))

        acquirer_id = post.get('payment_acquirer') and int(
            post.get('payment_acquirer'))
        acquirer = PA.search([('id', '=', acquirer_id)])

        tx = PT.search([
            ('is_wallet_transaction', '=', True),
            ('wallet_type', '=', 'credit'),
            ('partner_id', '=', partner.id),
            ('state', '=', 'draft')], limit=1)
        if tx:
            tx.amount = add_amount
            tx.acquirer_id = acquirer.id
        else:
            PT.create({
                'acquirer_id': acquirer.id,
                'type': 'form',
                'amount': add_amount,
                'currency_id': acquirer.company_id.currency_id.id,
                'partner_id': partner.id,
                'partner_country_id': partner.country_id.id,
                'is_wallet_transaction': True,
                'wallet_type': 'credit',
                'reference': request.env[
                    'payment.transaction'].sudo().get_next_wallet_reference(),
            })
        acquirers = request.env['payment.acquirer'].sudo().search([
            ('website_published', '=', True),
            ('is_wallet_acquirer', '=', True)])

        values = dict()
        values['form_acquirers'] = [acq for acq in acquirers if
                                    acq.payment_flow == 'form' and
                                    acq.view_template_id]
        currency_id = request.website.get_current_pricelist().currency_id.id
        base_url = request.env['ir.config_parameter'].sudo().get_param(
            'web.base.url')
        for acq in values['form_acquirers']:
            acq.form = acq.with_context(
                submit_class='btn btn-primary',
                submit_txt=_('Add Money')).sudo().render(
                    '/',
                    add_amount,
                    currency_id,
                    partner_id=request.env.user.partner_id.id,
                    values={
                        'return_url': base_url + '/wallet/payment/validate',
                    }
                )
            vals = {
                'wallet_bal': request.env.user.partner_id.wallet_balance,
                'acquirers': acquirers,
                'form_acquirers': values['form_acquirers'],
                'amount':add_amount,
            }
        return request.render("website_wallet.add_money_quantity", vals)

    @http.route(['/wallet/add/money/transaction'], type='http', auth="user",
                website=True)
    def wallet_add_money_txn_2(self, **post):
        user = request.env.user
        partner = user.partner_id
        PT = request.env['payment.transaction'].sudo()

        tx = PT.search([
            ('is_wallet_transaction', '=', True),
            ('wallet_type', '=', 'credit'),
            ('partner_id', '=', partner.id),
            ('state', '=', 'draft')], limit=1)

        # create an instance of the API class
        api_instance = swagger_client.PayInsRedsysApi()
        marketpayid = tx.marketpay_txnid

        try:
            # View a Redsys payment
            api_response = api_instance.pay_ins_redsys_redsys_get_payment(
                marketpayid)
        except ApiException as e:
            print("Exception when calling PayInsRedsysApi->pay_ins_redsys_"
                  "redsys_get_payment: %s\n" % e)

        if api_response.status == "FAILED":
            error = 'Received unrecognized RESULT for PayFlow Pro ' \
                    'payment %s: %s, set as error' % (
                tx.reference, api_response.result_message)
            _logger.info(error)
            tx.state = 'error'
            tx.state_message = error
        if api_response.status == "SUCCEEDED":
            _logger.info('%s Marketpay payment for tx %s: set as done' %
                         (tx.reference, api_response.result_message))
            tx.state = 'done'
            tx.date = datetime.now()
        values = {
            'tx_state': tx.state.capitalize(),
            'tx_amount': tx.amount,
            'tx_acquirer': tx.acquirer_id,
            'tx_reference': tx.acquirer_reference,
            'tx_time': tx.date,
            'wallet_bal': request.env.user.partner_id.wallet_balance,
        }
        return request.render("website_wallet.add_money_success", values)

    @http.route(['/wallet/payment/transaction'], type='json', auth="public",
                website=True)
    def wallet_payment_transaction(self, acquirer_id=None, amount=None,
                                   **post):
        user = request.env.user
        partner = user.partner_id
        PA = request.env['payment.acquirer'].sudo()
        PT = request.env['payment.transaction'].sudo()

        acquirer = PA.search([('id', '=', acquirer_id)])
        tx = PT.search([
            ('is_wallet_transaction', '=', True),
            ('wallet_type', '=', 'credit'),
            ('partner_id', '=', partner.id),
            ('state', '=', 'draft')], limit=1)
        if tx:
            tx.amount = amount
            tx.acquirer_id = acquirer.id
        else:
            tx = PT.create({
                'acquirer_id': acquirer.id,
                'type': 'form',
                'amount': amount,
                'currency_id': acquirer.company_id.currency_id.id,
                'partner_id': partner.id,
                'partner_country_id': partner.country_id.id,
                'is_wallet_transaction': True,
                'wallet_type': 'credit',
                'reference': request.env[
                    'payment.transaction'].get_next_wallet_reference(),
            })
        request.session['wallet_transaction_id'] = tx.id
        return {'tx_reference': tx.reference}

    @http.route(['/wallet/payment/validate'], type='http', auth="user",
                website=True)
    def wallet_payment_validate(self, **post):
        tx_id = request.session.get('wallet_transaction_id')
        if not tx_id:
            _logger.exception('Unable to find wallet transaction')

        PT = request.env['payment.transaction'].sudo()
        tx = PT.search([
            ('id', '=', tx_id), ('is_wallet_transaction', '=', True),
            ('wallet_type', '=', 'credit')], limit=1)
        if tx.acquirer_id.provider == 'paypal':
            if post.get('st') == 'Completed' and float(post.get('amt')) == \
                    float(tx.amount):
                _logger.info('PayPal payment successful.')
                tx.state = 'done'
                tx.acquirer_reference = post.get('tx')
                tx.date = datetime.now()
                return werkzeug.utils.redirect('/wallet/payment/confirmation')
            else:
                _logger.info('Received unrecognized RESULT for PayPal')
                tx.state = 'error'
                return werkzeug.utils.redirect('/wallet/add/money')
        print('Other Payment gateway_____________', post)

    @http.route(['/wallet/payment/confirmation'], type='http', auth="user",
                website=True)
    def wallet_payment_confirmation(self, **post):
        tx_id = request.session.get('wallet_transaction_id')
        if not tx_id:
            return werkzeug.utils.redirect('/wallet/add/money')

        PT = request.env['payment.transaction'].sudo()
        tx = PT.search([
            ('id', '=', tx_id), ('is_wallet_transaction', '=', True),
            ('wallet_type', '=', 'credit')], limit=1)

        values = {
            'tx_state': tx.state.capitalize(),
            'tx_amount': tx.amount,
            'tx_acquirer': tx.acquirer_id,
            'tx_reference': tx.acquirer_reference,
            'tx_time': tx.date,
            'wallet_bal': request.env.user.partner_id.wallet_balance,
        }
        return request.render("website_wallet.add_money_success", values)

    @http.route(['/wallet/transaction/history'], type='http', auth="user",
                website=True)
    def wallet_transaction_history(self, **post):
        user = request.env.user
        partner = user.partner_id
        vals = {
            'partner': partner
        }
        return request.render(
            "website_wallet.wallet_transaction_history", vals)

    @http.route(['/wallet/add/account'], type='http', auth="user",
                website=True)
    def wallet_add_account(self, **post):
        return request.render("website_wallet.add_account")


class PayflowProController(http.Controller):

    @http.route(['/payment/payflow_pro/s2s/create_json'], type='json',
                auth='public')
    def payflow_pro_s2s_create_json(self, **kwargs):
        data = kwargs['params']
        Acquirer = request.env['payment.acquirer'].browse(int(
            data.get('acquirer_id')))
        new_id = Acquirer.s2s_process(data)
        return new_id

    @http.route(['/payment/payflow_pro/s2s/create'], type='http',
                auth='public')
    def payflow_pro_s2s_create(self, **post):
        Acquirer = request.env['payment.acquirer'].browse(int(
            post.get('acquirer_id')))
        success = Acquirer.s2s_process(post)

        if success:
            url = '/my/payment_method'
            if post.get('return_url'):
                url = post.get('return_url')
            return werkzeug.utils.redirect(url)
        else:
            return werkzeug.utils.redirect('/my/payment_method/invalid')

    @http.route(['/payment/payflow_pro/s2s/feedback'])
    def feedback(self, **post):
        if not post:
            return werkzeug.utils.redirect('/')
        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', post.get('reference'))], limit=1)
        response = tx.payflow_pro_s2s_do_transaction(post)

        if not response:
            return werkzeug.utils.redirect(
                '/my/payment_method?return_url=/shop/payment')

        _logger.info('Data received from Payflow Pro %s',
                     pprint.pformat(response))
        tx.s2s_feedback(response, 'payflow_pro')
        return werkzeug.utils.redirect('/shop/payment/validate')


class WebsiteSale(WebsiteSale):
    @http.route(['/shop/wallet/pay'], type='http', auth="public", website=True)
    def shop_wallet_pay(self, **post):
        order = request.website.sale_get_order()
        if not order:
            return request.redirect('/shop/cart')

        if order.wallet_txn_id:
            return request.redirect('shop/payment')
        res = order.action_wallet_pay()
        if res and order.wallet_txn_id.amount == round(
                order.order_line[0].product_uom_qty, 2):
            # Traspasar fondos del wallet del usuario al wallet del proyecto
            order.wallet_txn_id.sudo().state = 'done'
            tx = order.wallet_txn_id
            if tx.state == 'done':
                _logger.info('Wallet transaction completed, %s (ID %s)',
                             tx.sale_order_ids and tx.sale_order_ids[0].name,
                             tx.sale_order_ids and tx.sale_order_ids[0].id)
                order.with_context(send_email=True).action_confirm()
                order.wallet_txn_id.sudo().write({'state': 'done'})
                if request.env['ir.config_parameter'].sudo().get_param(
                        'website_sale.automatic_invoice', default=False):
                    tx._generate_and_pay_invoice()
                request.session['sale_order_id'] = None
                request.session['sale_transaction_id'] = None
                return request.redirect('/shop/confirmation')
        else:
            # Order Partial Payment Flow
            return request.redirect('/shop/payment')

    def _get_shop_payment_values(self, order, **kwargs):
        values = dict(
            website_sale_order=order,
            errors=[],
            partner=order.partner_id.id,
            order=order,
            payment_action_id=request.env.ref(
                'payment.action_payment_acquirer').id,
            return_url='/shop/payment/validate',
            bootstrap_formatting= True
        )
        domain = expression.AND([
            ['&', '&', ('website_published', '=', True),
             ('company_id', '=', order.company_id.id),
             ('is_wallet_acquirer', '=', False)],
            ['|', ('website_id', '=', False),
             ('website_id', '=', request.website.id)],
            ['|', ('specific_countries', '=', False),
             ('country_ids', 'in', [order.partner_id.country_id.id])]
        ])
        acquirers = request.env['payment.acquirer'].search(domain)

        values['access_token'] = order.access_token
        values['acquirers'] = [
            acq for acq in acquirers if
            (acq.payment_flow == 'form' and acq.view_template_id) or (
                    acq.payment_flow == 's2s' and
                    acq.registration_view_template_id)]
        values['tokens'] = request.env['payment.token'].search(
            [('partner_id', '=', order.partner_id.id),
             ('acquirer_id', 'in', acquirers.ids)])
        return values

    @http.route('/shop/payment/validate', type='http', auth="public",
                website=True)
    def payment_validate(self, transaction_id=None, sale_order_id=None,
                         **post):
        """ Method that should be called by the server when receiving an update
        for a transaction. State at this point :

         - UDPATE ME
        """
        if sale_order_id is None:
            order = request.website.sale_get_order()
        else:
            partner_id = request.env.user.partner_id.id
            sale_order_id = request.env['sale.order'].search(
                [('partner_id', '=', partner_id)],
                order='date_order desc',
                limit=1
            )
            order = request.env['sale.order'].sudo().browse(sale_order_id)
            assert order.id == request.session.get(sale_order_id)

        if transaction_id:
            tx = request.env['payment.transaction'].sudo().browse(
                transaction_id)
            assert tx in order.transaction_ids()
        elif order:
            tx = order.get_portal_last_transaction()
        else:
            tx = None

        # Override for confirm wallet payment transaction
        if order.wallet_txn_id:
            order.wallet_txn_id.sudo().state = 'done'

        if not order or (order.amount_total and not tx):
            return request.redirect('/shop')

        # clean context and session, then redirect to the confirmation page
        request.website.sale_reset()
        if tx and tx.state == 'draft':
            return request.redirect('/shop')

        PaymentProcessing.remove_payment_transaction(tx)
        return request.redirect('/shop/confirmation')

    @http.route(['/shop/cart'], type='http', auth="public", website=True)
    def cart(self, access_token=None, revive='', **post):
        """
        Redirect to shop
        """
        return request.redirect('/shop')

    @http.route(['/shop/cart/update'], type='http', auth="public",
                methods=['POST'], website=True, csrf=False)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        """No cart allowed so delete orders on cart"""
        sale_order = request.website.sale_get_order(force_create=True)
        if sale_order.state == 'draft':
            sale_order.order_line.unlink()
        if sale_order.state != 'draft':
            request.session['sale_order_id'] = None
            sale_order = request.website.sale_get_order(force_create=True)

        product_custom_attribute_values = None
        if kw.get('product_custom_attribute_values'):
            product_custom_attribute_values = json.loads(
                kw.get('product_custom_attribute_values'))

        no_variant_attribute_values = None
        if kw.get('no_variant_attribute_values'):
            no_variant_attribute_values = json.loads(
                kw.get('no_variant_attribute_values'))

        sale_order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
        )
        return request.redirect("/shop/payment")

    @http.route(['/shop/confirmation'], type='http', auth="public",
                website=True)
    def payment_confirmation(self, **post):
        # sale_order_id = request.session.get('sale_last_order_id')
        partner_id = request.env.user.partner_id.id
        sale_order_id = request.env['sale.order'].search(
            [('partner_id', '=', partner_id)],
            order='date_order desc',
            limit=1
        )
        if sale_order_id:
            # order = request.env['sale.order'].sudo().browse(sale_order_id)
            return request.render("website_wallet.calma_sale_confirmation",
                                  {'order': sale_order_id})
        else:
            return request.redirect('/shop')
