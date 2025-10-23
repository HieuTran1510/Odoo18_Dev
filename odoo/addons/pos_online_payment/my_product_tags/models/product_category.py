# my_product_tags/models/product_category.py
from odoo import models, fields

class ProductCategory(models.Model):
    _inherit = 'product.category'

    # Danh sách user được gắn với category này (dùng chung bảng trung gian)
    assigned_user_ids = fields.Many2many(
        'res.users',
        'product_category_user_rel',
        'categ_id', 'user_id',
        string='Users with Access'
    )
