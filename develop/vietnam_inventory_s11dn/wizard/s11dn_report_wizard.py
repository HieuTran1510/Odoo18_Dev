import io
import base64
from odoo import models, fields, api

class VietnamS11DNReportWizard(models.TransientModel):
    _name = 'vietnam.s11dn.report.wizard'
    _description = 'Bảng kê nhập - xuất - tồn hàng hóa (S11-DN)'

    # Các trường trong wizard
    date_from = fields.Datetime('Từ ngày', required=True)
    date_to = fields.Datetime('Đến ngày', required=True)
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    warehouse_id = fields.Many2one('stock.warehouse', string='Kho hàng')
    location_id = fields.Many2one('stock.location', string='Địa điểm kho')
    product_categ_id = fields.Many2one('product.category', string='Nhóm sản phẩm')

    # Nút "In" (tạm đóng popup)
    def action_print_report(self):
        return {'type': 'ir.actions.act_window_close'}

    # Nút "Xuất Excel"
    def action_export_excel(self):
        import xlsxwriter
        from datetime import datetime

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('S11-DN')

        # --- Định dạng ---
        bold = workbook.add_format({'bold': True})
        center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
        border = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        money = workbook.add_format({'num_format': '#,##0', 'border': 1, 'align': 'right'})
        text = workbook.add_format({'border': 1, 'align': 'left'})
        title = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 14})

        # --- Header ---
        sheet.merge_range('C2:H2', f"Công ty: {self.company_id.name}", bold)
        if self.company_id.street:
            sheet.merge_range('C3:H3', f"Địa chỉ: {self.company_id.street}", bold)

        sheet.merge_range('K2:M2', "Mẫu S11-DN", center)
        sheet.merge_range('K3:M3', "(Ban hành theo TT 200/2014/TT-BTC)", center)

        # --- Tiêu đề báo cáo ---
        sheet.merge_range('A6:M6', "BẢNG KÊ NHẬP - XUẤT - TỒN HÀNG HÓA", title)
        date_str = f"Từ ngày: {self.date_from.strftime('%d/%m/%Y %H:%M:%S')} - Đến ngày: {self.date_to.strftime('%d/%m/%Y %H:%M:%S')}"
        sheet.merge_range('A7:M7', date_str, center)

        # --- Thông tin kho ---
        warehouse_name = self.warehouse_id.name or "Tất cả"
        location_name = self.location_id.name or "Tất cả"
        sheet.write('B8', f"Kho hàng: {warehouse_name}")
        sheet.write('B9', f"Địa điểm kho: {location_name}")
        sheet.write('M9', "Tiền tệ: VND")

        # --- Tiêu đề cột ---
        headers = [
            "Mã vật tư", "Sản phẩm", "ĐVT",
            "Số dư đầu kỳ (SL)", "Số dư đầu kỳ (TT)",
            "Nhập trong kỳ (SL)", "Nhập trong kỳ (TT)",
            "Xuất trong kỳ (SL)", "Xuất trong kỳ (TT)",
            "Tồn cuối kỳ (SL)", "Tồn cuối kỳ (TT)"
        ]
        sheet.write_row('A11', headers, border)

        # --- Dữ liệu thực tế ---
        domain = []
        if self.warehouse_id:
            domain.append(('warehouse_id', '=', self.warehouse_id.id))
        if self.product_categ_id:
            domain.append(('product_id.categ_id', '=', self.product_categ_id.id))

        # Lấy dữ liệu từ stock.quant (tồn cuối)
        quants = self.env['stock.quant'].search(domain)
        data_lines = []
        for q in quants:
            data_lines.append({
                'code': q.product_id.default_code or '',
                'name': q.product_id.name,
                'uom': q.product_uom_id.name,
                'begin_qty': 0,  # bạn có thể thêm tính toán tồn đầu kỳ
                'begin_value': 0,
                'in_qty': 0, 'in_value': 0,
                'out_qty': 0, 'out_value': 0,
                'end_qty': q.quantity,
                'end_value': q.quantity * q.product_id.standard_price,
            })

        # --- Ghi dữ liệu ra Excel ---
        row = 11
        for line in data_lines:
            sheet.write(row, 0, line['code'], text)
            sheet.write(row, 1, line['name'], text)
            sheet.write(row, 2, line['uom'], text)
            sheet.write_number(row, 3, line['begin_qty'], border)
            sheet.write_number(row, 4, line['begin_value'], money)
            sheet.write_number(row, 5, line['in_qty'], border)
            sheet.write_number(row, 6, line['in_value'], money)
            sheet.write_number(row, 7, line['out_qty'], border)
            sheet.write_number(row, 8, line['out_value'], money)
            sheet.write_number(row, 9, line['end_qty'], border)
            sheet.write_number(row, 10, line['end_value'], money)
            row += 1

        workbook.close()
        output.seek(0)
        xlsx_data = output.read()
        output.close()

        # --- Tạo file attachment ---
        export_id = self.env['ir.attachment'].create({
            'name': 'Bang_ke_nhap_xuat_ton_S11DN.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(xlsx_data),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{export_id.id}?download=true",
            'target': 'self',
        }
