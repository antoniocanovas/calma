# -*- coding: utf-8 -*-

{
    'name': "Calma_grid",

    'summary': """
        Sync partner, company, wallets""",

    'description': """
       Módulo para llevar las operaciones sobre usuarios y wallets a marketpay.
       Adicionalmente cambia el aspecto del grid y preview de productos 
    """,

    'author': "Pedro Guirao",
    'website': "https://ingenieriacloud.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Tools',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['base','sale','sale_management','website','website_sale','contacts'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/shop_inh_product_view.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'installable': True,
    'application': True,
    'auto_install': False,
}