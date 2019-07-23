{
    'name': "Calma_grid",
    'summary': """
        Conjunto de cambios visuales para los productos, grid, ....""",
    'author': "Pedro Guirao",
    'license': 'AGPL-3',
    'website': "https://ingenieriacloud.com",
    'category': 'Tools',
    'version': '12.0.1.1.0',
    'depends': [
        'marketpay_sync',
        'sale_management',
        'website_sale',
    ],
    'data': [
        'views/product_template_views.xml',
        'views/website_templates.xml',
        'views/templates.xml',
    ],
    'installable': True,
}
