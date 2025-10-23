from odoo import fields, models
from datetime import datetime



class AccountReportsWizard(models.TransientModel):
    _name = 'account.reports.wizard'

    data = fields.Char('Data', default='Do you want to print report Partner Ledger Detail PDF', readonly=True)

    def action_confirm(self):
        options = None
        if self._context.get('options'):
            options = self._context.get('options')
        xml_id = self.env.ref('biz_detail_of_receivable_report.account_reports_report_pdf')
        xml_id.write({'name': 'Tổng-công-nợ-phải-thu-%s' % (datetime.now().strftime('%d-%m-%Y'))})
        return xml_id.report_action(docids=self, data=options)