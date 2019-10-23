{
    'name': "Calma Grid",
    'summary': """
        Conjunto de cambios visuales para los productos, grid, ....""",
    'author': "Pedro Guirao",
    'license': 'AGPL-3',
    'website': "https://ingenieriacloud.com",
    'category': 'Tools',
    'version': '12.0.2.6.1',
    'depends': [
        'sale_management',
        'sale_order_line_input',
        'website_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/crowdfunding_options_views.xml',
        'views/product_template_views.xml',
        'views/website_templates.xml',
        'views/templates.xml',
    ],
    'installable': True,
}
