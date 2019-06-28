{
    'name': "Calma_grid",
    'summary': """
        Conjunto de cambios visuales para los productos, grid, ....""",
    'description': """  
    """,
    'author': "Pedro Guirao",
    'license': 'AGPL-3',
    'website': "https://ingenieriacloud.com",
    'category': 'Tools',
    'version': '1.0',
    'depends': ['sale_management','website_sale','contacts'],
    'data': [
        'views/shop_inh_product_view.xml',
        'views/template_inh_cart.xml',
        'views/templates.xml',
    ],
    'installable': True,
    'application': True,
}