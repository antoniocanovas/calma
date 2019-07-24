{
    'name': "Calma Grid",
    'summary': """
        Conjunto de cambios visuales para los productos, grid, ....""",
    'author': "Pedro Guirao",
    'license': 'AGPL-3',
    'website': "https://ingenieriacloud.com",
    'category': 'Tools',
    'version': '12.0.1.3.0',
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
    ],
    'installable': True,
}
