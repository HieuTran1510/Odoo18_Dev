from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"

    # Tiền tệ của hạn mức (mặc định = tiền tệ công ty hiện tại)
    credit_limit_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
        string="Credit Limit Currency",
        help="Currency used to express the customer's credit limit.",
    )

    # Hạn mức tín dụng do bạn đặt cho từng khách hàng
    credit_limit = fields.Monetary(
        string="Credit Limit",
        currency_field="credit_limit_currency_id",
        help="Maximum allowed exposure for this customer.",
        tracking=True,
    )

    @api.constrains("credit_limit")
    def _check_credit_limit_non_negative(self):
        for p in self:
            if p.credit_limit and p.credit_limit < 0:
                raise ValidationError(_("Credit limit cannot be negative."))
