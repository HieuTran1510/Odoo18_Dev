# my_product_tags/models/product_template.py
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    allowed_user_ids = fields.Many2many(
        'res.users',
        'product_template_user_access_rel',
        'product_tmpl_id', 'user_id',
        string='Người dùng ngoại lệ'
    )
    x_owner_company_id = fields.Many2one(
        'res.company',
        string='Công ty sở hữu',
        help="Công ty sở hữu đối tác này."
    )
    x_shared_company_ids = fields.Many2many(
        'res.company',
        string='Công ty chia sẻ',
        help="Các công ty được phép truy cập đối tác này."
    )
