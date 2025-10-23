from odoo import fields, models, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    ref_partner = fields.Char('Ref Partner', compute='_compute_ref_vat_partner', store=True)
    vat_partner = fields.Char('Vat Partner', compute='_compute_ref_vat_partner', store=True)

    @api.depends('partner_id')
    def _compute_ref_vat_partner(self):
        for rec in self:
            if rec.partner_id:
                rec.ref_partner = rec.partner_id.ref or ''
                rec.vat_partner = rec.partner_id.vat or ''
