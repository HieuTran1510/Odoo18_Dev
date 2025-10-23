{
    "name": "YTV Credit Limit",
    "version": "18.0.1.0.0",
    "summary": "Block Sales Order confirmation when credit limit is exceeded; approvers can override.",
    "author": "Hieu Tran",
    "website": "https://example.com",
    "license": "LGPL-3",
    "depends": ["sale", "account"],
    "data": [
        "security/credit_groups.xml",
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/sale_order_views.xml"
    ],
    "installable": True,
    "application": False
}
