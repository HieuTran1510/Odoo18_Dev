from odoo import fields, models, api
from datetime import datetime


class DebtNotifWizard(models.TransientModel):
    _name = 'debt.notif.wizard'

    data = fields.Char('Data', default='Do you want to print report Partner Ledger Detail PDF', readonly=True)


    def action_print(self):
        options = None
        if self._context.get('options'):
            options = self._context.get('options')
        xml_id = self.env.ref('biz_detail_of_receivable_report.debt_notification_report_pdf')
        # xml_id.write({'name': 'Tổng-công-nợ-phải-thu-%s' % (datetime.now().strftime('%d-%m-%Y'))})
        return xml_id.report_action(docids=self, data=options)