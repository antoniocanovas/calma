{
    'name': "Marketpay Sync",
    'summary': """
        Sync partner, company, wallets""",
    'author': "Pedro Guirao",
    'license': 'AGPL-3',
    'website': "https://ingenieriacloud.com",
    'category': 'Tools',
    'version': '12.0.1.4.0',
    'depends': [
        'sale_management',
        'website_sale',
        'website_wallet',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/templates.xml',
        'views/crowdfunding_options_views.xml',
    ],
    'installable': True,
}
