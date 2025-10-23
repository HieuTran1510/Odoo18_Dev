from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Tiền tệ công ty để quy đổi/so sánh thống nhất
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # Hiển thị tham khảo trên SO
    so_total_receivable = fields.Monetary(
        string="Total Receivable",
        currency_field="company_currency_id",
        compute="_compute_credit_info",
        store=False,
        readonly=True,
        help="Customer's current total receivable (in company currency).",
    )
    so_credit_limit = fields.Monetary(
        string="Credit Limit",
        currency_field="company_currency_id",
        compute="_compute_credit_info",
        store=False,
        readonly=True,
        help="Customer's credit limit converted to company currency.",
    )

    @api.depends("partner_id", "date_order", "company_id")
    def _compute_credit_info(self):
        for so in self:
            partner = so.partner_id.commercial_partner_id
            # Đảm bảo lấy công nợ theo ngữ cảnh công ty của đơn
            total_recv = partner.with_company(so.company_id).credit

            # Quy đổi hạn mức về tiền công ty
            limit = partner.credit_limit or 0.0
            limit_cur = partner.credit_limit_currency_id or so.company_currency_id
            limit_ccy = limit_cur._convert(
                limit,
                so.company_currency_id,
                so.company_id,
                so.date_order or fields.Date.today(),
            )

            so.so_total_receivable = total_recv
            so.so_credit_limit = limit_ccy

    def _check_credit_before_confirm(self):
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id

        # Không đặt hạn mức => không kiểm tra
        if not partner.credit_limit:
            return

        # Đơn giá trị chưa thuế, quy đổi về tiền công ty theo ngày đơn
        order_amt_ccy = self.currency_id._convert(
            self.amount_untaxed,
            self.company_currency_id,
            self.company_id,
            self.date_order or fields.Date.today(),
        )

        # Hạn mức quy đổi về tiền công ty
        limit_ccy = (partner.credit_limit_currency_id or self.company_currency_id)._convert(
            partner.credit_limit,
            self.company_currency_id,
            self.company_id,
            self.date_order or fields.Date.today(),
        )

        # Công nợ phải thu hiện tại theo công ty của đơn
        total_recv = partner.with_company(self.company_id).credit

        # overage = (Receivable + SO_untaxed_ccy) - CreditLimit_ccy
        overage = (total_recv + order_amt_ccy) - limit_ccy

        # Chặn nếu vượt hạn mức và user KHÔNG có nhóm Approver
        if overage > 0 and not self.env.user.has_group(
            "sale_credit_gate_so_only.group_so_credit_approver"
        ):
            raise UserError(
                _("Credit limit exceeded for %s.\n"
                  "Overage: %s %.2f > 0.\n"
                  "Ask a Sales Credit Approver to confirm.")
                % (
                    partner.display_name,
                    self.company_currency_id.symbol or "",
                    overage,
                )
            )

    def action_confirm(self):
        for so in self:
            so._check_credit_before_confirm()
        return super().action_confirm()
