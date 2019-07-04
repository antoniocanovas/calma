# Copyright 2019 Pedro Baños - Ingeniería Cloud
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    'name': 'Acquirer Marketpay',
    'category': 'Payment Acquirer',
    'summary': 'Payment Acquirer: marketpay Implementation',
    'version': '12.0.1.0.0',
    'author': "Pedro Baños,",
    'depends': [
        'payment',
        'website_sale',
    ],
    'data': [
        'views/marketpay_templates.xml',
        'views/payment_acquirer_views.xml',
        'views/payment_marketpay_templates.xml',
        'data/payment_marketpay.xml'
    ],
    'license': 'AGPL-3',
    'installable': True,
}
