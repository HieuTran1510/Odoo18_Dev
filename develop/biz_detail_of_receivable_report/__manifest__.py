# -*- coding: utf-8 -*-
{
    'name': "Bizapps - Details Of Receivable By Customer",
    'description': "",
    'category': 'Accountant',
    'summary': 'Report on customer receivable',
    'version': '18.0.0.1',
    'website': 'https://bizapps.vn/ung-dung',
    'license': 'OPL-1',
    'depends': [
        'account',
        'account_reports',
    ],
    'data': [
        'views/partner_ledger.xml',
        'views/account_report_actions.xml',
        'views/menuitem.xml',

        'security/ir.model.access.csv',

        'report/account_reports_template.xml',
        'report/debt_notif_template.xml',
        'report/report_action.xml',

    ],
    "installable": True,
    "application": True,
    'auto_install': False,
    "private": False,
    "authorise": "",
}
