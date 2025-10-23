from odoo import api, fields, models, _
from datetime import datetime, timedelta
from .common import _get_number_split, set_column_widths
from odoo.tools import formatLang


class AccountReportsPdf(models.AbstractModel):
    _name = "report.biz_detail_of_receivable_report.report_account_reports"
    _description = "Account Reports Report"


    def get_format_data_lines(self, report_id, lines):
        res = {}
        col_stt = {
            'nk': 1,
            'account': 2,
            'ref': 3,
            'deadline': 4,
            'sk': 5,
            'debit': 6,
            'credit': 7,
            'amount': 8,
            'balance': 9,
        }
        i = 10
        stt = 1
        y_offset = 0
        total_initial_balance_credit = total_initial_balance_debit = total_credit = total_debit = 0
        total_balance_credit = total_balance_debit = 0
        for line in lines:
            if line.get('level') and line['level'] == 2 and not line.get('parent_id'):
                open_balance = [x for x in lines if
                                x.get('parent_id') == line.get('id') and x.get('level') and x.get('level') == 2]
                incurred = [x for x in lines if
                            x.get('parent_id') == line.get('id') and x.get('level') and x.get('level') == 4]
                ending_balance = [x for x in lines if
                                  x.get('parent_id') == line.get('id') and x.get('level') and x.get('level') == 3]

                col_open = []
                if open_balance:
                    for open in open_balance:
                        arr = open.get('columns', [])
                        col_open.append(arr)
                open_filter = []
                if col_open:
                    for column in col_open[0]:
                        if column.get('name') or column.get('name') == '':
                            open_filter.append(column)
                initial_balance_str, initial_balance_num, initial_balance_num_symbol = False, False, False
                if open_filter:
                    initial_balance_str, initial_balance_num, initial_balance_num_symbol = _get_number_split(
                        open_filter[-1].get('name'))

                col_incurred = [incur.get('columns', []) for incur in incurred] if incurred else []
                initial_balance_1 = 0
                initial_balance_2 = 0
                for column in col_incurred:
                    get_column = column[-4:]
                    initial_balance_str_1, initial_balance_num_1, initial_balance_num_symbol_1 = _get_number_split(
                        get_column[0].get('name'))
                    initial_balance_str_2, initial_balance_num_2, initial_balance_num_symbol_2 = _get_number_split(
                        get_column[1].get('name'))
                    initial_balance_1 = initial_balance_1 + initial_balance_num_1
                    initial_balance_2 = initial_balance_2 + initial_balance_num_2

                col_ending = []
                if ending_balance:
                    for ending in ending_balance:
                        arr = ending.get('columns', [])
                        col_ending.append(arr)
                ending_filter = []
                if col_ending:
                    for column in col_ending[0]:
                        if column.get('name'):
                            ending_filter.append(column)
                balance_str, balance_num, balance_num_symbol = False, False, False
                if ending_filter:
                    balance_str, balance_num, balance_num_symbol = _get_number_split(ending_filter[-1].get('name'))

                res[y_offset] = {
                    'a': stt,
                    'b': line.get('ref') or '',
                    'c': line.get('name') or '',
                    'd': line.get('vat') or '',
                    '1': self.format_number(initial_balance_num) if initial_balance_num and initial_balance_num > 0 else '0',
                    '2': self.format_number(initial_balance_num) if initial_balance_num and initial_balance_num < 0 else '0',
                    '3': self.format_number(initial_balance_1),
                    '4': self.format_number(initial_balance_2),
                    '5': self.format_number(balance_num) if balance_num > 0 else '0',
                    '6': self.format_number(abs(balance_num)) if balance_num < 0 else '0',
                    'l': '',
                }
                if initial_balance_num >= 0:
                    total_initial_balance_credit += initial_balance_num
                else:
                    total_initial_balance_debit += abs(initial_balance_num)

                if balance_num >= 0:
                    total_balance_credit += balance_num
                else:
                    total_balance_debit += abs(balance_num)

                total_credit += initial_balance_1
                total_debit += initial_balance_2
                i += 1
                y_offset += 1
                stt += 1
        res[y_offset] = {
            'a': '',
            'b': '',
            'c': 'Tổng',
            'd': '',
            '1': self.format_number(total_initial_balance_credit),
            '2': self.format_number(total_initial_balance_debit),
            '3': self.format_number(total_credit),
            '4': self.format_number(total_debit),
            '5': self.format_number(total_balance_credit),
            '6': self.format_number(total_balance_debit),
            'l': '',
        }
        return res

    def format_number(self, number, blank_if_zero=False):
        if number == 0 and blank_if_zero:
            return ''
        if self.env.context.get('no_format'):
            return number
        formatted_number = formatLang(self.env, number, currency_obj=False)
        if self.env.lang == 'vi_VN':
            formatted_number = formatted_number.replace(',00', '')
        else:
            formatted_number = formatted_number.replace('.00', '').replace(',', '.')
        return formatted_number

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
        docs = self.env['account.reports.wizard'].search([], limit=1)
        docids = docs.id
        options = data
        title = self.get_title_column_report(options)
        report_id = self.env['account.report'].browse(int(options['report_id']))
        print_options = report_id._get_options(previous_options=options)
        lines = report_id._get_lines(print_options)
        res = self.get_format_data_lines(report_id, lines)
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
            'doc_model': 'account.report.wizard',
            'docs': docs,
            'title': title,
            'get_company_address': self.get_company_address,
            'lines': res,
            'date_from': from_date,
            'date_to': to_date,
            'format_date': self.format_date
        }