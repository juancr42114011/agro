# -*- coding: utf-8 -*-
{
    'name': "Agropecuaria",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",
    'license': "LGPL-3",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.4',

    # any module necessary for this one to work correctly
    'depends': ['account','imporgesa','stock'],

    # always loaded
    'data': [
        #'security/ir.model.access.csv',
        #'security/presupuesto_venta_security.xml',
        'views/views.xml',
        'views/templates.xml',
        'views/product_template_views.xml',
        'data/account_account_data.xml',
        'data/product_template_data.xml',
        'data/account_journal_data.xml',
        #'data/ir_sequence_data.xml',
        #'views/presupuesto_venta_views.xml',
        'report/sale_report.xml',
        #'wizard/purchase_order_views_wizard.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'agro/static/src/scss/report_product_label.scss',
        ],
    },
}
