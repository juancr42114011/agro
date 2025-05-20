# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools import date_utils
from dateutil.relativedelta import relativedelta
import base64
import io
import xlrd
from odoo.tools.misc import xlsxwriter

class LibroContableReport(models.TransientModel):
    _name = "libro_contable.report"
    _description = "Reporte de Libros Contables"
    
    def _get_start_mondth_date(self):
        today = fields.Date.today() - relativedelta(months=1)
        return date_utils.start_of(today, 'month')
        
    def _get_end_mondth_date(self):
        today = fields.Date.today() - relativedelta(months=1)
        return date_utils.end_of(today, 'month')




    company_id = fields.Many2one('res.company', string='Company', readonly=True, default=lambda self: self.env.company)
    journal_ids = fields.Many2many('account.journal',
                                   'account_report_libro_contable_journal_rel',
                                   'account_id',
                                   'journal_id',
                                   string='Diarios',
                                   domain="[('company_id', '=', company_id)]"
                                   )
    date_from = fields.Date(string='Start Date', required=True, default=_get_start_mondth_date)
    date_to = fields.Date(string='End Date', required=True, default=_get_end_mondth_date)
    target_move = fields.Selection([('posted', 'Asientos Publicados'),
                                    ('all', 'Todos los Asientos'),
                                    ], string='Target Moves', required=True, default='posted')
    libro = fields.Selection([('diario', 'Diario'),
                            ('mayor','Mayor'),
                            ], string='Libro Contable', required=True, default='diario')
    folio = fields.Integer(string="Folio")
    
    archivo = fields.Binary('Archivo')

    def _build_contexts(self, data):
        result = {}
        result['journal_ids'] = 'journal_ids' in data['form'] and data['form']['journal_ids'] or False
        result['state'] = 'target_move' in data['form'] and data['form']['target_move'] or ''
        result['date_from'] = data['form']['date_from'] or False
        result['date_to'] = data['form']['date_to'] or False
        result['strict_range'] = True if result['date_from'] else False
        result['libro'] = data['form']['libro'] or False
        result['company_id'] = data['form']['company_id'][0] or False
        return result

    def check_report(self):
        self.ensure_one()
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['company_id','date_from', 'date_to', 'journal_ids', 'target_move','libro','folio'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang') or 'en_US')
        return self._print_report(data)

    def _print_report(self, data):
        libro = data['form'].get('libro')
        if libro=='diario':
            return self.env.ref('agro.action_report_agro_diario').report_action(self, data=data, config=False)
        else:
            return self.env.ref('agro.action_report_agro_libro_mayor').report_action(self, data=data, config=False)

    def export_xls(self):
        self.ensure_one()
        context = self._context
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['company_id','date_from', 'date_to', 'journal_ids', 'target_move','libro','folio'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang') or 'en_US')
        f = io.BytesIO()
        workbook = xlsxwriter.Workbook(f)
        if self.libro == 'diario':
            self.env['report.agro.libro_contable_diario_xlsx'].generate_xlsx_report(workbook, data, data_report=[])            
        else:
            print(data['form'])
            self.env['report.agro.libro_contable_mayor_xlsx'].generate_xlsx_report(workbook, data, data_report=[])

        workbook.close()
        datos = base64.b64encode(f.getvalue())
        self.write({'archivo':datos, })
        return {
                'name': 'FEC',
                'type': 'ir.actions.act_url',
                'url': "web/content/?model=libro_contable.report&id=" + str(self.id) + "&filename_field=filename&field=archivo&download=true&filename=" + 'libro_contable',
                'target': 'self',
            }
