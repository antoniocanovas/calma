# -*- coding: utf-8 -*-
#################################################################################
# Author      : Kanak Infosystems LLP. (<http://kanakinfosystems.com/>)
# Copyright(c): 2012-Present Kanak Infosystems LLP.
# All Rights Reserved.
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <http://kanakinfosystems.com/license>
#################################################################################

{
    'name': 'Website Wallet',
    'description': 'Website wallet for faster checkout process',
    'category': 'Ecommerce',
    'summary': 'Allows customers to add money to the wallet and use it later on',
    'version': '1.0',
    'license': 'OPL-1',
    'author': 'Kanak Infosystems LLP.',
    'website': 'http://www.kanakinfosystems.com',
    'depends': ['website_sale', 'payment_paypal', 'website_payment'],
    'data': [
        'views/website_paypal_views.xml',
        'views/website_wallet_views.xml',
        'views/website_wallet_templates.xml',
        'security/ir.model.access.csv',
        'data/website_wallet_demo.xml',
    ],
    'installable': True,
    'application': True,
    'support': 'info@kanakinfosystems.com',
    'price': 99,
    'currency': 'EUR',
    'images': ['static/description/wallet.png'],
    'live_test_url': 'https://youtu.be/4IVr_Y-7oi0'
}
