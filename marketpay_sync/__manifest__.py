{
    'name': "marketpay_sync",
    'summary': """
        Sync partner, company, wallets""",
    'author': "Pedro Guirao",
    'license': 'AGPL-3',
    'website': "https://ingenieriacloud.com",
    'category': 'Tools',
    'version': '12.0.1.0.0',
    'depends': ['base','sale','sale_management','website_sale',
                'website_wallet','contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/products_template_crowf_view.xml',
        'views/company_marketpay_view.xml',
        'views/partner_marketpay_view.xml',
        'views/portal_templates_inh.xml',
        'views/opciones_crowd_view.xml',
    ],
    'installable': True,
    'application': True,
}