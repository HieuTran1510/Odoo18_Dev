from odoo import api, fields, models, _
from datetime import datetime, timedelta
from .common import _get_number_split, set_column_widths
from odoo.tools import formatLang
from odoo.addons.biz_detail_of_receivable_report.config import amount_to_text
import re


class DebtNotifPdf(models.AbstractModel):
    _name = "report.biz_detail_of_receivable_report.debt_notif_reports"
    _description = "Debt Notification Report"


    def format_number(self, number, blank_if_zero=False):
        if number:
            if self.env.context.get('no_format'):
                return number
            formatted_number = formatLang(self.env, number, currency_obj=False)
            if self.env.lang == 'vi_VN':
                formatted_number = formatted_number.replace(',00', '')
            else:
                formatted_number = formatted_number.replace('.00', '').replace(',', '.')
            return formatted_number
        if number == 0.0:
            return '0'

    def get_company_address(self, company):
        address = ''
        if company:
            if company.street:
                address += company.street
            if company.street2:
                address += len(address) > 0 and ', ' + company.street2 or company.street2
            if company.city:
                address += len(address) > 0 and ', ' + company.city or company.city
            if company.state_id:
                address += len(address) > 0 and ', ' + company.state_id.name or company.state_id.name
            if company.country_id:
                address += len(address) > 0 and ', ' + company.country_id.name or company.country_id.name
        return address

    def format_date(self, date):
        result = 'Ngày.....tháng.....năm.....'
        if date:
            result = date.strftime('Ngày %d tháng %m năm %Y')
        return result

    def get_infor_customer(self, parent, name_partner=False, address=False, vat=False):
        result = ''
        if parent:
            id = False
            try:
                id = re.search(r'\d+', parent.get('id')).group()
            except Exception as e:
                print("WARNING : {}".format(e))
            if id:
                partner = self.env['res.partner'].browse(int(id))
                if partner:
                    if name_partner:
                        result = partner.name
                    if vat:
                        result = partner.vat
                    if address:
                        result = self.get_company_address(partner)
        return result

    def amount2text(self, number, integer=False):
        if integer:
            return amount_to_text(number).split(' đồng')[0].lower()
        return amount_to_text(number)

    def get_line_table(self, parent, lines):
        if lines and parent:
            res = {}
            y_offset = 0
            open_balance = [x for x in lines if
                            x.get('parent_id') == parent.get('id') and x.get('level') and x.get('level') == 2]
            incurred = [x for x in lines if
                        x.get('parent_id') == parent.get('id') and x.get('level') and x.get('level') == 4]
            initial_balance_str, receivables, initial_balance_num_symbol = False, False, False
            for open in open_balance:
                col_open = []
                arr = open.get('columns', [])
                col_open.append(arr)
                open_filter = []
                if col_open:
                    for column in col_open[0]:
                        if column.get('name') or column.get('name') == '':
                            open_filter.append(column)
                if open_filter:
                    initial_balance_str, receivables, initial_balance_num_symbol = _get_number_split(
                        open_filter[-1].get('name'))
                res[y_offset] = {
                    'a': '',
                    'b': '',
                    'c': 'Dư đầu kỳ',
                    '1': None,
                    '2': None,
                    '3': receivables if receivables else 0,
                    '4': None,
                    'is_bold': False,
                    'ending_balance': False,
                }
                y_offset += 1
            account_move = []
            for incur in incurred:
                split_string = incur.get('id').split('~')
                id = split_string[-1]
                if incur.get('caret_options') == 'account.payment':
                    move_line = self.env['account.move.line'].browse(int(id))
                    if move_line:
                        res[y_offset] = {
                            'a': move_line.payment_id.date.strftime('%d/%m/%Y'),
                            'b': move_line.payment_id.name,
                            'c': move_line.payment_id.ref,
                            '1': None,
                            '2': None,
                            '3': None,
                            '4': move_line.payment_id.amount,
                            'is_bold': False,
                            'ending_balance': False,
                        }
                        y_offset += 1
                if incur.get('caret_options') == 'account.move.line':
                    move_line = self.env['account.move.line'].browse(int(id))
                    if move_line.move_id.id not in account_move:
                        account_move.append(move_line.move_id.id)
                        for line in move_line.move_id.invoice_line_ids:
                            name = move_line.move_id.vat_sinvoice_number or ''
                            receivables = line.price_total
                            res[y_offset] = {
                                'a': move_line.date.strftime('%d/%m/%Y'),
                                'b': name,
                                'c': line.name,
                                '1': line.quantity,
                                '2': line.price_unit,
                                '3': receivables,
                                '4': None,
                                'is_bold': False,
                                'ending_balance': False,
                            }
                            y_offset += 1
                    else:
                        continue
            total_receivables = total_payment_deduction = 0
            opening_balance = 0
            for rec in res.values():
                if rec['3'] and rec['c'] == 'Dư đầu kỳ':
                    opening_balance += rec['3']
                if rec['3'] and rec['c'] != 'Dư đầu kỳ':
                    total_receivables += rec['3']
                if rec['4']:
                    total_payment_deduction += rec['4']
            res[y_offset] = {
                'a': '',
                'b': '',
                'c': 'Cộng phát sinh',
                '1': '',
                '2': '',
                '3': total_receivables,
                '4': total_payment_deduction,
                'is_bold': True,
                'ending_balance': False,
            }
            y_offset += 1
            res[y_offset] = {
                'a': '',
                'b': '',
                'c': 'Dư cuối kỳ',
                '1': '',
                '2': '',
                '3': opening_balance + total_receivables - total_payment_deduction,
                '4': '',
                'is_bold': True,
                'ending_balance': True,
            }
            y_offset += 1
            return res

    def get_lasted_lines(self, lines):
        result = 0
        for rec in lines.values():
            if rec.get('ending_balance'):
                result = rec.get('3')
        return result

    def get_title_column_report(self, options):
        title = ''
        if options and options.get('account_type'):
            type = []
            for opt in options.get('account_type'):
                if opt.get('selected') == True:
                    type.append(opt.get('id'))
            if len(type) == 1:
                if type[0] == 'is_customer':
                    title = 'Phải thu'
                if type[0] == 'is_vendor':
                    title = 'Phải trả'
            else:
                title = 'Phải thu/phải trả'
        return title


    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['debt.notif.wizard'].search([], limit=1)
        docids = docs.id
        options = data
        title = self.get_title_column_report(options)
        report_id = self.env['account.report'].browse(int(options['report_id']))
        print_options = report_id._get_options(previous_options=options)
        lines = report_id._get_lines(print_options)
        lines_parent = [x for x in lines if (x.get('level') and x.get('level') == 2) and not x.get('parent_id')]
        from_date = options['date']['date_from'] if options.get('date') and options['date'].get('date_from') else ''
        to_date = options['date']['date_to'] if options.get('date') and options['date'].get('date_to') else ''
        if from_date:
            from_date_date = datetime.strptime(from_date, "%Y-%m-%d")
            from_date = from_date_date.strftime('%d/%m/%Y')
        if to_date:
            to_date_date = datetime.strptime(to_date, "%Y-%m-%d")
            to_date = to_date_date.strftime('%d/%m/%Y')
        return {
            'doc_ids': [docids],
            'doc_model': 'debt.notif.wizard',
            'docs': docs,
            'title': title,
            'get_company_address': self.get_company_address,
            'lines_parent': lines_parent,
            'date_from': from_date,
            'date_to': to_date,
            'lines': lines,
            'format_date': self.format_date,
            'get_line_table': self.get_line_table,
            'get_infor_customer': self.get_infor_customer,
            'format_number': self.format_number,
            'amount2text': self.amount2text,
            'get_lasted_lines': self.get_lasted_lines,
        }