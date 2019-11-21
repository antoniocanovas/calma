# Copyright 2019 Pedro Baños - Ingeniería Cloud
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    'name': "Marketpay Sync",
    'summary': """
        Sync partner, company, wallets""",
    'author': "Pedro Guirao",
    'license': 'AGPL-3',
    'website': "https://ingenieriacloud.com",
    'category': 'Tools',
    'version': '12.0.2.8.1',
    'depends': [
        'sale_management',
        'website_sale',
        'website_wallet',
        'contacts',
    ],
    'data': [
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/templates.xml',
    ],
    'installable': True,
}
