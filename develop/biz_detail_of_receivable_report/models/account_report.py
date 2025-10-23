# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _, osv, _lt
import io
from odoo.tools.misc import xlsxwriter
from odoo.exceptions import UserError, ValidationError
import json
from .common import _get_number_split, set_column_widths
from datetime import datetime
from odoo.tools import formatLang
import pprint
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
import markupsafe




class AccountReport(models.Model):
    _inherit = "account.report"

    custom_button_receiveble = fields.Boolean('Custom button')
    custom_filter_partner = fields.Boolean('Custom Filter partner')

    def get_default_report_filename(self, extension):
        """The default to be used for the file when downloading pdf,xlsx,..."""
        self.ensure_one()
        name = self.name + '_' + '%s' % (datetime.now().strftime('%d_%m_%Y'))
        return f"{name.lower().replace(' ', '_')}.{extension}"


    def _init_options_buttons(self, options, previous_options=None):
        super(AccountReport, self)._init_options_buttons(options, previous_options)
        if self.custom_button_receiveble:
            options['buttons'] = [
                {'name': _('PDF'), 'sequence': 15, 'action': 'export_to_pdf_new'},
                {'name': _('XLSX'), 'sequence': 30, 'action': 'print_customer_accounts_receivable_summary_xlsx',
                 'action_param': 'export_to_xlsx', 'file_export_type': _('XLSX')},
                {'name': _('DEBT NOTICE'), 'sequence': 35, 'action': 'export_to_pdf_new_customer'},
                {'name': _('REFRESH'), 'sequence': 100, 'action': 'refresh_report'},
            ]
            options['custom_button_receiveble'] = True

    def _expand_unfoldable_line(self, expand_function_name, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        if not expand_function_name:
            raise UserError(_("Trying to expand a line without an expansion function."))

        if not progress:
            progress = {column_group_key: 0 for column_group_key in options['column_groups']}

        expand_function = self._get_custom_report_function(expand_function_name, 'expand_unfoldable_line')
        expansion_result = expand_function(line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=unfold_all_batch_data)

        rslt = expansion_result['lines']
        if expansion_result.get('has_more'):
            # We only add load_more line for groupby
            next_offset = offset + expansion_result['offset_increment']
            rslt.append(self._get_load_more_line(next_offset, line_dict_id, expand_function_name, groupby, expansion_result.get('progress', 0), options))

        # In some specific cases, we may want to add lines that are always at the end. So they need to be added after the load more line.
        if expansion_result.get('after_load_more_lines'):
            rslt.extend(expansion_result['after_load_more_lines'])

        return self._add_totals_below_sections(rslt, options)

    def _add_totals_below_sections(self, lines, options):
        """ Returns a new list, corresponding to lines with the required total lines added as sublines of the sections it contains.
        """
        if not self.env.company.totals_below_sections or options.get('ignore_totals_below_sections'):
            return lines

        # Gather the lines needing the totals
        lines_needing_total_below = set()
        for line_dict in lines:
            line_markup = self._get_markup(line_dict['id'])

            if line_markup != 'total':
                # If we are on the first level of an expandable line, we arelady generate its total
                if line_dict.get('unfoldable') or (line_dict.get('unfolded') and line_dict.get('expand_function')):
                    lines_needing_total_below.add(line_dict['id'])

                # All lines that are parent of other lines need to receive a total
                line_parent_id = line_dict.get('parent_id')
                if line_parent_id:
                    lines_needing_total_below.add(line_parent_id)

        # Inject the totals
        if lines_needing_total_below:
            lines_with_totals_below = []
            totals_below_stack = []
            for line_dict in lines:
                while totals_below_stack and not line_dict['id'].startswith(totals_below_stack[-1]['parent_id']):
                    lines_with_totals_below.append(totals_below_stack.pop())

                lines_with_totals_below.append(line_dict)

                if line_dict['id'] in lines_needing_total_below and any(col.get('no_format') is not None for col in line_dict['columns']):
                    line_dict['class'] = f"{line_dict.get('class', '')} o_account_reports_totals_below_sections"
                    totals_below_stack.append(self._generate_total_below_section_line(line_dict))

            if self.custom_button_receiveble:
                while totals_below_stack:
                    lines_with_totals_below.append(totals_below_stack)
                except_lines = []
                parent_id = []
                for line in lines:
                    if line.get('level') and line.get('level') == 4:
                        except_lines.append(line)

                debit = 0
                credit = 0
                for li in except_lines:
                    parent_id.append(li.get('parent_id'))
                    columns = li['columns']
                    columns_debit = columns[5]
                    columns_credit = columns[6]
                    debit += columns_debit.get('no_format')
                    credit += columns_credit.get('no_format')
                parent = parent_id[0] if parent_id else False
                new_line = self._genarate_new_total_line(debit, credit, parent, except_lines)
                if new_line:
                    lines_with_totals_below.append(new_line)

                return lines_with_totals_below
            else:
                while totals_below_stack:
                    lines_with_totals_below.append(totals_below_stack.pop())

                return lines_with_totals_below

        return lines

    def _init_options_partner(self, options, previous_options=None):
        if self.custom_filter_partner:
            if not self.filter_partner:
                return

            options['partner'] = True
            previous_partner_ids = previous_options and previous_options.get('partner_ids') or []
            options['partner_categories'] = previous_options and previous_options.get('partner_categories') or []

            selected_partner_ids = [int(partner) for partner in previous_partner_ids]
            # search instead of browse so that record rules apply and filter out the ones the user does not have access to
            selected_partners = selected_partner_ids and self.env['res.partner'].search([('id', 'in', selected_partner_ids)]) or self.env['res.partner']
            options['selected_partner_ids'] = selected_partners.mapped('name')
            options['partner_ids'] = selected_partners.ids

            selected_partner_category_ids = [int(category) for category in options['partner_categories']]
            selected_partner_categories = selected_partner_category_ids and self.env['res.partner.category'].browse(selected_partner_category_ids) or self.env['res.partner.category']
            options['selected_partner_categories'] = selected_partner_categories.mapped('name')
        else:
            options['partner'] = True
            options['partner_categories'] = []
            options['selected_partner_ids'] = []
            options['partner_ids'] = []
            options['selected_partner_categories'] = []
            return self.click_button_filter()


    def click_button_filter(self):
        self.custom_filter_partner = True
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


    def _genarate_new_total_line(self, debit, credit, parent_id, except_lines):
        if except_lines and parent_id:
            report = self.env['account.report']
            column_values = [{}, {}, {}, {}, {}, {}, {}, {}, {}]
            column_values[5] = {
                'name': self.format_value(debit, figure_type='monetary', blank_if_zero=False),
                'no_format': debit,
                'class': 'number',
            }
            column_values[6] = {
                'name': self.format_value(credit, figure_type='monetary', blank_if_zero=False),
                'no_format': credit,
                'class': 'number',
            }
            return {
                'id': report._get_generic_line_id(None, None, markup='total'),
                'name': _('Total Journal Items'),
                'class': 'total',
                'parent_id': parent_id,
                'level': 6,
                'columns': column_values,
            }

    def _init_options_account_type(self, options, previous_options=None):
        '''
        Initialize a filter based on the account_type of the line (trade/non trade, payable/receivable).
        Selects a name to display according to the selections.
        The group display name is selected according to the display name of the options selected.
        '''
        if not self.filter_account_type:
            return

        options['account_type'] = [
            {'id': 'trade_receivable', 'name': _("Receivable"), 'selected': True},
            {'id': 'non_trade_receivable', 'name': _("Non Trade Receivable"), 'selected': False},
            {'id': 'trade_payable', 'name': _("Payable"), 'selected': True},
            {'id': 'non_trade_payable', 'name': _("Non Trade Payable"), 'selected': False},
        ]
        if self.custom_button_receiveble:
            options['account_type'] = [
                {'id': 'is_customer', 'name': _("Is Customer"), 'selected': False},
                {'id': 'is_vendor', 'name': _("Is Vendor"), 'selected': False},
            ]
        if previous_options and previous_options.get('account_type'):
            previously_selected_ids = {x['id'] for x in previous_options['account_type'] if x.get('selected')}
            for opt in options['account_type']:
                opt['selected'] = opt['id'] in previously_selected_ids

        selected_options = {x['id']: x['name'] for x in options['account_type'] if x['selected']}
        selected_ids = set(selected_options.keys())
        display_names = []

        def check_if_name_applicable(ids_to_match, string_if_match):
            '''
            If the ids selected are part of a possible grouping,
                - append the name of the grouping to display_names
                - Remove the concerned ids
            ids_to_match : the ids forming a group
            string_if_match : the group's name
            '''
            if len(selected_ids) == 0:
                return
            if ids_to_match.issubset(selected_ids):
                display_names.append(string_if_match)
                for selected_id in ids_to_match:
                    selected_ids.remove(selected_id)

        check_if_name_applicable({'trade_receivable', 'trade_payable', 'non_trade_receivable', 'non_trade_payable'}, _("All receivable/payable"))
        check_if_name_applicable({'trade_receivable', 'non_trade_receivable'}, _("All Receivable"))
        check_if_name_applicable({'trade_payable', 'non_trade_payable'}, _("All Payable"))
        check_if_name_applicable({'trade_receivable', 'trade_payable'}, _("Trade Partners"))
        check_if_name_applicable({'non_trade_receivable', 'non_trade_payable'}, _("Non Trade Partners"))
        check_if_name_applicable({'is_customer', 'is_vendor'}, _("Customer and Vendor"))
        for sel in selected_ids:
            display_names.append(selected_options.get(sel))
        options['account_display_name'] = ', '.join(display_names)

    @api.model
    def _get_options_partner_is_customer(self, options):
        domain = []
        is_customer = options.get('is_customer', False)
        if is_customer:
            domain.append(('partner_id.is_customer', '=', True))
        return domain

    def _get_options_partner_is_vendor(self, options):
        domain = []
        is_vendor = options.get('is_vendor', False)
        if is_vendor:
            domain.append(('partner_id.is_vendor', '=', True))
        return domain

    def _get_options_account_type_domain(self, options):
        if options.get('custom_button_receiveble'):
            all_domains = [[('account_id.non_trade', '=', False), ('account_id.account_type', '=', 'asset_receivable')],
                           [('account_id.non_trade', '=', True), ('account_id.account_type', '=', 'asset_receivable')],
                           [('account_id.non_trade', '=', False), ('account_id.account_type', '=', 'liability_payable')],
                           [('account_id.non_trade', '=', True), ('account_id.account_type', '=', 'liability_payable')]]
            selected_domains = []
            if not options.get('account_type') or len(options.get('account_type')) == 0:
                return []
            for opt in options.get('account_type', []):
                if opt['selected']:
                    if opt['id'] == 'is_customer':
                        options['is_customer'] = True
                    if opt['id'] == 'is_vendor':
                        options['is_vendor'] = True
                else:
                    if opt['id'] == 'is_customer':
                        options['is_customer'] = False
                    if opt['id'] == 'is_vendor':
                        options['is_vendor'] = False
            return osv.expression.OR(selected_domains or all_domains)
        else:
            all_domains = []
            selected_domains = []
            if not options.get('account_type') or len(options.get('account_type')) == 0:
                return []
            for opt in options.get('account_type', []):
                if opt['id'] == 'trade_receivable':
                    domain = [('account_id.non_trade', '=', False), ('account_id.account_type', '=', 'asset_receivable')]
                elif opt['id'] == 'trade_payable':
                    domain = [('account_id.non_trade', '=', False), ('account_id.account_type', '=', 'liability_payable')]
                elif opt['id'] == 'non_trade_receivable':
                    domain = [('account_id.non_trade', '=', True), ('account_id.account_type', '=', 'asset_receivable')]
                elif opt['id'] == 'non_trade_payable':
                    domain = [('account_id.non_trade', '=', True), ('account_id.account_type', '=', 'liability_payable')]
                if opt['selected']:
                    selected_domains.append(domain)
                all_domains.append(domain)
            return osv.expression.OR(selected_domains or all_domains)

    def refresh_report(self, options):
        self.custom_filter_partner = False
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def print_customer_accounts_receivable_summary_xlsx(self, options, file_generator):
        self.ensure_one()
        options['is_customer'] = True
        options['unfold_all'] = True
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                 'options': json.dumps(options),
                 'file_generator': file_generator,
             }
        }

    def _get_slytes(self, workbook):
        unit_address = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 13, 'text_wrap': True, 'align': 'left'})
        date = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'right'})
        date_value = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'center'})

        sub_title = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'center', 'italic': True})
        # col_center =
        result = {
            'INTRO': {
                'unit': unit_address,
                'address': unit_address,
                'report_name': workbook.add_format(
                    {'font_name': 'Times New Roman', 'bold': True, 'font_size': 16, 'text_wrap': True,
                     'align': 'center'}),
                'from_date': date,
                'to_date': date,
                'from_date_value': date_value,
                'to_date_value': date_value,
                'sub_title': sub_title
            },
            'TABLE': {
                'col_title': workbook.add_format(
                    {'font_name': 'Times New Roman', 'bg_color': '#5499C7', 'bottom': 1, 'top': 1, 'left': 1,
                     'right': 1, 'font_size': 13, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                     'font_color': '#17202A'}),
                'col_center': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'center', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'text_wrap': True}),
                'col_center_bold': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'center', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'text_wrap': True, 'bold': True}),
                'col_right_bold': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'right', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'text_wrap': True, 'bold': True}),
                'col_right': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'right', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'text_wrap': True}),
                'col_left': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'left', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'text_wrap': True}),
                'col_left_bold': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'left', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'bold': True, 'text_wrap': True})
            },
            'CONCLUSION': {
                'date': workbook.add_format(
                    {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'center',
                     'italic': True}),
                'sign_title': workbook.add_format(
                    {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'center',
                     'bold': True})
            }
        }

        return result

    def export_to_pdf_new(self, options):
        print_mode_self = self.with_context(print_mode=True)
        options['unfold_all'] = True
        ctx = {'options': options}
        account_reports = self.env['account.reports.wizard'].create({'data': 'test'})
        return account_reports.with_context(ctx).action_confirm()

    def export_to_pdf_new_customer(self, options):
        # print_mode_self = self.with_context(print_mode=True)
        options['unfold_all'] = True
        ctx = {'options': options}
        debt_notif = self.env['debt.notif.wizard'].create({'data': 'test'})
        return debt_notif.with_context(ctx).action_print()


    def _get_options_domain(self, options, date_scope):
        domain = super(AccountReport, self)._get_options_domain(options, date_scope)
        domain += self._get_options_partner_is_customer(options)
        domain += self._get_options_partner_is_vendor(options)
        return domain

    def get_title_column_report(self, options):
        title = ''
        if options and options.get('account_type'):
            type = []
            for opt in options.get('account_type'):
                if opt.get('selected') == True:
                    type.append(opt.get('id'))
            if len(type) == 1:
                if type[0] == 'is_customer':
                    title = 'PHẢI THU'
                if type[0] == 'is_vendor':
                    title = 'PHẢI TRẢ'
            else:
                title = 'PHẢI THU/PHẢI TRẢ'
        return title



    def export_to_xlsx(self, options, response=None):
        def write_with_colspan(sheet, x, y, value, colspan, style):
            if colspan == 1:
                sheet.write(y, x, value, style)
            else:
                sheet.merge_range(y, x, y, x + colspan - 1, value, style)
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })
        from_date = options['date']['date_from'] if options.get('date') and options['date'].get('date_from') else ''
        to_date = options['date']['date_to'] if options.get('date') and options['date'].get('date_to') else ''
        slyte = self._get_slytes(workbook)
        title = self.get_title_column_report(options)
        if from_date:
            from_date_date = datetime.strptime(from_date, "%Y-%m-%d")
            from_date = from_date_date.strftime('%d/%m/%Y')
        if to_date:
            to_date_date = datetime.strptime(to_date, "%Y-%m-%d")
            to_date = to_date_date.strftime('%d/%m/%Y')
        sheet = workbook.add_worksheet(self.name[:31])

        date_default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2, 'num_format': 'yyyy-mm-dd'})
        date_default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'num_format': 'yyyy-mm-dd'})
        default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'})
        title_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'bottom': 2})
        level_0_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#666666'})
        level_1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 1, 'font_color': '#666666'})
        level_2_col1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_2_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_2_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_3_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        level_3_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_3_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'})

        #Set the first column width to 50
        if not options.get('is_customer'):
            sheet.set_column(0, 0, 50)

            y_offset = 0
            x_offset = 1 # 1 and not 0 to leave space for the line name
            print_mode_self = self.with_context(no_format=True, print_mode=True, prefetch_fields=False)
            print_options = print_mode_self._get_options(previous_options=options)
            lines = self._filter_out_folded_children(print_mode_self._get_lines(print_options))

            # Add headers.
            # For this, iterate in the same way as done in main_table_header template
            column_headers_render_data = self._get_column_headers_render_data(print_options)
            for header_level_index, header_level in enumerate(print_options['column_headers']):
                for header_to_render in header_level * column_headers_render_data['level_repetitions'][header_level_index]:
                    colspan = header_to_render.get('colspan', column_headers_render_data['level_colspan'][header_level_index])
                    write_with_colspan(sheet, x_offset, y_offset, header_to_render.get('name', ''), colspan, title_style)
                    x_offset += colspan
                if print_options['show_growth_comparison']:
                    write_with_colspan(sheet, x_offset, y_offset, '%', 1, title_style)
                y_offset += 1
                x_offset = 1

            for subheader in column_headers_render_data['custom_subheaders']:
                colspan = subheader.get('colspan', 1)
                write_with_colspan(sheet, x_offset, y_offset, subheader.get('name', ''), colspan, title_style)
                x_offset += colspan
            y_offset += 1
            x_offset = 1

            for column in print_options['columns']:
                colspan = column.get('colspan', 1)
                write_with_colspan(sheet, x_offset, y_offset, column.get('name', ''), colspan, title_style)
                x_offset += colspan
            y_offset += 1

            if print_options.get('order_column'):
                lines = self._sort_lines(lines, print_options)

            # Add lines.
            for y in range(0, len(lines)):
                level = lines[y].get('level')
                if lines[y].get('caret_options'):
                    style = level_3_style
                    col1_style = level_3_col1_style
                elif level == 0:
                    y_offset += 1
                    style = level_0_style
                    col1_style = style
                elif level == 1:
                    style = level_1_style
                    col1_style = style
                elif level == 2:
                    style = level_2_style
                    col1_style = 'total' in lines[y].get('class', '').split(' ') and level_2_col1_total_style or level_2_col1_style
                elif level == 3:
                    style = level_3_style
                    col1_style = 'total' in lines[y].get('class', '').split(' ') and level_3_col1_total_style or level_3_col1_style
                else:
                    style = default_style
                    col1_style = default_col1_style

                #write the first column, with a specific style to manage the indentation
                cell_type, cell_value = self._get_cell_type_value(lines[y])
                if cell_type == 'date':
                    sheet.write_datetime(y + y_offset, 0, cell_value, date_default_col1_style)
                else:
                    sheet.write(y + y_offset, 0, cell_value, col1_style)

                #write all the remaining cells
                columns = lines[y]['columns']
                if print_options['show_growth_comparison'] and 'growth_comparison_data' in lines[y]:
                    columns += [lines[y].get('growth_comparison_data')]
                for x, column in enumerate(columns, start=1):
                    cell_type, cell_value = self._get_cell_type_value(column)
                    if cell_type == 'date':
                        sheet.write_datetime(y + y_offset, x + lines[y].get('colspan', 1) - 1, cell_value, date_default_style)
                    else:
                        sheet.write(y + y_offset, x + lines[y].get('colspan', 1) - 1, cell_value, style)
        else:
            unit = "Đơn vị: %s" % (self.env.company.name if self.env.company else '')
            address = "Địa chỉ: %s" % (self.get_address_by(self.env.company) if self.env.company else '')
            sheet.merge_range('A1:J1', unit, slyte['INTRO']['unit'])
            sheet.merge_range('A2:J2', address, slyte['INTRO']['address'])

            sheet.set_row(3, 20)
            report_name = 'BẢNG TỔNG HỢP CÔNG NỢ %s KHÁCH HÀNG' % (title)
            sheet.merge_range('A4:J4', report_name, slyte['INTRO']['report_name'])


            sheet.write('E6', 'Từ ngày:', slyte['INTRO']['from_date'])
            sheet.write('E7', 'Đến ngày:', slyte['INTRO']['to_date'])

            sheet.write('F6', from_date, slyte['INTRO']['from_date_value'])
            sheet.write('F7', to_date, slyte['INTRO']['to_date_value'])

            # ----- Body------#
            # super_columns = self._get_super_columns(options)

            # if not options.get('unfold_all'):
            #     raise UserError("You haven't unfolded all, please check again.")

            sheet.merge_range('A9:A10', 'TT', slyte['TABLE']['col_title'])
            sheet.merge_range('B9:B10', 'Mã khách hàng', slyte['TABLE']['col_title'])
            sheet.merge_range('C9:C10', 'Tên khách hàng', slyte['TABLE']['col_title'])
            sheet.merge_range('D9:D10', 'Mã số thuế', slyte['TABLE']['col_title'])
            sheet.merge_range('E9:F9', 'Số dư đầu kỳ', slyte['TABLE']['col_title'])
            sheet.write('E10', 'Nợ', slyte['TABLE']['col_title'])
            sheet.write('F10', 'Có', slyte['TABLE']['col_title'])
            sheet.merge_range('G9:H9', 'Phát sinh', slyte['TABLE']['col_title'])
            sheet.write('G10', 'Nợ', slyte['TABLE']['col_title'])
            sheet.write('H10', 'Có', slyte['TABLE']['col_title'])
            sheet.merge_range('I9:J9', 'Số dư cuối kỳ', slyte['TABLE']['col_title'])
            sheet.write('I10', 'Nợ', slyte['TABLE']['col_title'])
            sheet.write('J10', 'Có', slyte['TABLE']['col_title'])
            sheet.merge_range('K9:K10', 'Ghi chú', slyte['TABLE']['col_title'])

            column_widths = {'A:A': 4, 'B:B': 12, 'C:C': 50, 'D:D': 12, 'E:E': 15, 'F:F': 15, 'G:G': 15, 'H:H': 15,
                             'I:I': 15, 'J:J': 15}
            set_column_widths(sheet, column_widths)
            # body:
            lines = self._get_lines(options)
            i = 10
            stt = 1
            parent_dict = {}
            total_initial_balance_credit = total_initial_balance_debit = total_credit = total_debit = 0
            total_balance_credit = total_balance_debit = 0

            def get_format(*arguments):
                normal_style = {'font_name': 'Times New Roman', 'align': 'left', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'text_wrap': True}
                for arg in arguments:
                    normal_style.update(arg)
                return workbook.add_format(normal_style)

            for line in lines:
                if line.get('level') and line['level'] == 2 and not line.get('parent_id'):
                    open_balance = [x for x in lines if x.get('parent_id') == line.get('id') and x.get('level') and x.get('level') == 2]
                    incurred = [x for x in lines if x.get('parent_id') == line.get('id') and x.get('level') and x.get('level') == 4]
                    ending_balance = [x for x in lines if x.get('parent_id') == line.get('id') and x.get('level') and x.get('level') == 3]

                    sheet.write(i, 0, stt, slyte['TABLE']['col_center'])
                    sheet.write(i, 1, line.get('ref') or '', slyte['TABLE']['col_left'])
                    sheet.write(i, 2, line.get('name'), get_format({'text_wrap': True, 'border': True, 'align': 'left'}))
                    sheet.write(i, 3, line.get('vat') or '', slyte['TABLE']['col_left'])

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
                    sheet.write(i, 4, self.format_number(initial_balance_num) if initial_balance_num and initial_balance_num > 0 else '0',
                                slyte['TABLE']['col_right'])
                    sheet.write(i, 5, self.format_number(abs(initial_balance_num)) if initial_balance_num and initial_balance_num < 0 else '0',
                                slyte['TABLE']['col_right'])

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
                    sheet.write(i, 6, self.format_number(initial_balance_1), slyte['TABLE']['col_right'])
                    sheet.write(i, 7, self.format_number(initial_balance_2), slyte['TABLE']['col_right'])

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

                    sheet.write(i, 8, self.format_number(balance_num) if balance_num > 0 else '0',
                                slyte['TABLE']['col_right'])
                    sheet.write(i, 9, self.format_number(abs(balance_num)) if balance_num < 0 else '0',
                                slyte['TABLE']['col_right'])

                    sheet.write(i, 10, '', slyte['TABLE']['col_left'])

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
                    stt += 1

            # TOTAL
            sheet.write(i, 0, '', slyte['TABLE']['col_center'])
            sheet.write(i, 1, '', slyte['TABLE']['col_center'])
            sheet.write(i, 2, 'Tổng', slyte['TABLE']['col_center_bold'])
            sheet.write(i, 3, '', slyte['TABLE']['col_center'])
            sheet.write(i, 4, self.format_number(total_initial_balance_credit), slyte['TABLE']['col_right_bold'])
            sheet.write(i, 5, self.format_number(total_initial_balance_debit), slyte['TABLE']['col_right_bold'])
            sheet.write(i, 6, self.format_number(total_credit), slyte['TABLE']['col_right_bold'])
            sheet.write(i, 7, self.format_number(total_debit), slyte['TABLE']['col_right_bold'])
            sheet.write(i, 8, self.format_number(total_balance_credit), slyte['TABLE']['col_right_bold'])
            sheet.write(i, 9, self.format_number(total_balance_debit), slyte['TABLE']['col_right_bold'])
            sheet.write(i, 10, '', slyte['TABLE']['col_left'])

            # Footer
            i += 3
            now = fields.datetime.now()
            footer_date = 'Ngày %s tháng %s năm %s' % (now.day, now.month, now.year)
            sheet.merge_range(i, 7, i, 9, footer_date, slyte['CONCLUSION']['date'])
            i += 1
            sheet.merge_range(i, 0, i, 2, 'Người lập biểu', slyte['CONCLUSION']['sign_title'])
            sheet.merge_range(i, 3, i, 5, 'Phụ trách kế toán', slyte['CONCLUSION']['sign_title'])
            sheet.merge_range(i, 7, i, 9, 'Kế toán trưởng', slyte['CONCLUSION']['sign_title'])
            i += 1
            sheet.merge_range(i, 7, i, 9, '(Ký, họ tên)', slyte['CONCLUSION']['date'])

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return {
            'file_name': self.get_default_report_filename('xlsx'),
            'file_content': generated_file,
            'file_type': 'xlsx',
        }


    def get_address_by(self, company):
        address_parts = []

        if company and company.street:
            address_parts.append(company.street)

        if company and company.street2:
            address_parts.append(company.street2)

        if company and company.city:
            address_parts.append(company.city)

        if company and company.state_id:
            address_parts.append(company.state_id.name)

        if company and company.country_id:
            address_parts.append(company.country_id.name)

        address = ', '.join(address_parts)
        return address

    def _get_slytes(self, workbook):
        unit_address = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 13, 'text_wrap': True, 'align': 'left'})
        date = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'right'})
        date_value = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'center'})

        sub_title = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'center', 'italic': True})
        # col_center =
        result = {
            'INTRO': {
                'unit': unit_address,
                'address': unit_address,
                'report_name': workbook.add_format(
                    {'font_name': 'Times New Roman', 'bold': True, 'font_size': 16, 'text_wrap': True,
                     'align': 'center'}),
                'from_date': date,
                'to_date': date,
                'from_date_value': date_value,
                'to_date_value': date_value,
                'sub_title': sub_title
            },
            'TABLE': {
                'col_title': workbook.add_format(
                    {'font_name': 'Times New Roman', 'bg_color': '#5499C7', 'bottom': 1, 'top': 1, 'left': 1,
                     'right': 1, 'font_size': 13, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                     'font_color': '#17202A'}),
                'col_center': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'center', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'text_wrap': True}),
                'col_center_bold': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'center', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'text_wrap': True, 'bold': True}),
                'col_right_bold': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'right', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'text_wrap': True, 'bold': True}),
                'col_right': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'right', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'text_wrap': True}),
                'col_left': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'left', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1}),
                'col_left_bold': workbook.add_format(
                    {'font_name': 'Times New Roman', 'align': 'left', 'valign': 'vcenter', 'bottom': 1, 'top': 1,
                     'left': 1, 'right': 1, 'bold': True})
            },
            'CONCLUSION': {
                'date': workbook.add_format(
                    {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'center',
                     'italic': True}),
                'sign_title': workbook.add_format(
                    {'font_name': 'Times New Roman', 'font_size': 13, 'text_wrap': True, 'align': 'center',
                     'bold': True})
            }
        }

        return result

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

