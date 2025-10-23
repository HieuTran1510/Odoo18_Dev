from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Công ty sở hữu duy nhất
    x_owner_company_id = fields.Many2one(
        'res.company',
        string='Công ty sở hữu',
        help="Công ty sở hữu đối tác này."
    )

    # Các công ty được chia sẻ
    x_shared_company_ids = fields.Many2many(
        'res.company',
        string='Công ty chia sẻ',
        help="Các công ty được phép truy cập đối tác này."
    )
