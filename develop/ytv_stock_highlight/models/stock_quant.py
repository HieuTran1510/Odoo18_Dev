# -*- coding: utf-8 -*-
from odoo import api, fields, models

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    x_removal_date = fields.Date(
        string='Removal Date (related)',
        related='lot_id.removal_date',
        store=True,
        readonly=True,
    )
