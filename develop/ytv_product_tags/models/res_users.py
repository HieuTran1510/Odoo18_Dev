# my_product_tags/models/res_users.py
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Các nhóm (category) user được cấp quyền
    product_domain_ids = fields.Many2many(
        'product.category',
        'product_category_user_rel',
        'user_id', 'categ_id',
        string="Product Groups"
    )
