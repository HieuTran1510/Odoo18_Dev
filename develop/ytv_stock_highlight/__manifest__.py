# -*- coding: utf-8 -*-
{
    'name': 'Stock Quant Expiry Highlight',
    'summary': 'Highlight đỏ dòng stock.quant khi Removal Date quá hạn, áp dụng cho mọi quyền',
    'version': '18.0.1.0.0',  # chỉnh 14/15/16/17 tùy phiên bản Odoo của bạn
    'category': 'Inventory/Stock',
    'author': 'Your Company',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['stock'],  # yêu cầu app 'stock'
    'data': [
        'views/stock_quant_views.xml',
    ],
    'installable': True,
    'application': False,
}
