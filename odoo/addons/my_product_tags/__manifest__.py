{
    'name': 'My Product Tags',
    'summary': 'Adds a many2many field for product tags.',
    'version': '18.0.1.0.0',
    'depends': ['product', 'sale'],
    'data': [
       'security/product_rule.xml',
        'views/product_views.xml',
        'views/res_users_views.xml',
        'views/product_category_views.xml'
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}