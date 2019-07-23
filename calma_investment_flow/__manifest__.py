{
    'name': "Calma_investment_flow",
    'summary': """
        Proceso de inversión para crowfunding""",
    'description': """ 
        Elimina de la vista el carrito de compra,
        Añade un controller para confirmar la transacción.
        Modifica website_sale para evitar el uso de carrito eliminando las 
        líneas de venta previamente existentes en un presupuesto cada vez que 
        invertimos 
        en un producto. 
    """,
    'author': "Pedro Guirao",
    'license': 'AGPL-3',
    'website': "https://ingenieriacloud.com",
    'category': 'Tools',
    'version': '1.0',
    'depends': ['sale_management','website_sale'],
    'data': [
        'views/template_inh_cart.xml',
    ],
    'installable': True,
    'application': True,
}