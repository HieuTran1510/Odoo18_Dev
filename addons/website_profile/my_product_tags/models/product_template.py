# my_product_tags/models/product_template.py
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    allowed_user_ids = fields.Many2many(
        'res.users',
        'product_template_user_access_rel',
        'product_tmpl_id', 'user_id',
        string='Extra Allowed Users'
    )
