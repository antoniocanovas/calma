# Copyright 2019 Pedro Baños - Ingeniería Cloud
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    'name': "Calma Grid",
    'summary': """
        Conjunto de cambios visuales para los productos, grid, ....""",
    'author': "Pedro Guirao",
    'license': 'AGPL-3',
    'website': "https://ingenieriacloud.com",
    'category': 'Tools',
    'version': '12.0.2.9.2',
    'depends': [
        'sale_management',
        'website_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/crowdfunding_options_views.xml',
        'views/product_template_views.xml',
        'views/website_templates.xml',
        'views/templates.xml',
        'views/sale_order_line_views.xml',
    ],
    'installable': True,
}
