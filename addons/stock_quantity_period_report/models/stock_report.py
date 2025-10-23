from odoo import models, fields, api

class StockQuantityPeriodReport(models.TransientModel):
    _name = 'stock.quantity.period.report'
    _description = 'Stock Quantity Report in Period'

    date_from = fields.Date(string="From Date", required=True)
    date_to = fields.Date(string="To Date", required=True)

    def action_get_report(self):
        self.ensure_one()
        query = """
            SELECT
                sm.product_id,
                pt.name as product_name,
                sum(CASE WHEN sm.location_id != sl.id THEN sm.product_uom_qty ELSE 0 END) as qty_in,
                sum(CASE WHEN sm.location_dest_id != sl.id THEN sm.product_uom_qty ELSE 0 END) as qty_out
            FROM stock_move sm
            JOIN product_product pp ON sm.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN stock_location sl ON sl.usage = 'internal'
            WHERE sm.date BETWEEN %s AND %s
              AND sm.state = 'done'
              AND (sm.location_id = sl.id OR sm.location_dest_id = sl.id)
            GROUP BY sm.product_id, pt.name
            ORDER BY pt.name;
        """
        self.env.cr.execute(query, (self.date_from, self.date_to))
        result = self.env.cr.fetchall()
        # Bạn có thể in ra hoặc trả kết quả về view/report
        for row in result:
            _logger.info(f"Product: {row[1]}, Nhập: {row[2]}, Xuất: {row[3]}")
        return True
