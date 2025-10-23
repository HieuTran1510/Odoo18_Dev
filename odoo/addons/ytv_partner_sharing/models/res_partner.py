# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = "res.partner"
    # Nếu liên hệ cần chia sẻ cho nhiều công ty → để trống company_id và chọn ở đây
    x_ytv_allowed_company_ids = fields.Many2many(
        "res.company",
        string="Công ty chia sẻ",
        help="Nếu liên hệ chia sẻ cho nhiều công ty, để trống Company và chọn danh sách công ty tại đây."
    )
