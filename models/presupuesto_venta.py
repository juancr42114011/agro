# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

import datetime
from dateutil.relativedelta import relativedelta

from odoo.tools.misc import xlsxwriter
from xlsxwriter.utility import xl_col_to_name
import base64
import io
import logging

class PresupuestoVenta(models.Model):
    _name = "presupuesto.venta"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Presupuesto de Venta"
    _order = 'id desc'
    _mail_post_access = 'read'
    _check_company_auto = True
    
    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }
    
    name = fields.Char(string='Number', 
                       copy=False, 
                       readonly=True, 
                       store=True, 
                       index=True,
                       )
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)
    date = fields.Date(
        string='Date',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        copy=False,
        tracking=True,
        default=fields.Date.context_today
    )
    date_start = fields.Date(string='Fecha Inicio',)
    date_end = fields.Date(string='Fecha Fin',)
    state = fields.Selection(selection=[
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('cancel', 'Cancelled'),
        ], string='Status', required=True, readonly=True, copy=False, tracking=True,
        default='draft')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, states=READONLY_STATES, default=lambda self: self.env.company.id)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, states=READONLY_STATES,
        default=lambda self: self.env.company.currency_id.id)
    order_line = fields.One2many('presupuesto.venta.line', 'order_id', string='Order Lines', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)
    user_id = fields.Many2one(
        'res.users', string='Usuario', index=True, tracking=True,
        default=lambda self: self.env.user, check_company=True)
    
    archivo = fields.Binary('Archivo', filters='.xls')
    
    @api.model
    def create(self, vals):
        company_id = vals.get('company_id', self.default_get(['company_id'])['company_id'])
        self_comp = self.with_company(company_id)
        if vals.get('name', 'New') == 'New':
            seq_date = None
            if 'date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date']))
            vals['name'] = self_comp.env['ir.sequence'].next_by_code('presupuesto.venta', sequence_date=seq_date) or '/'
        
        res = super(PresupuestoVenta, self_comp).create(vals)
        return res

    def ventas_product(self, product_id, date_start, date_end):
        venta = {}
        venta_producto = self.env['account.move.line'].read_group(
                domain=[('product_id', '=', product_id),('move_id.invoice_date','>=',date_start),('move_id.invoice_date','<=',date_end),
                        ('move_id.journal_id.type','=','sale')],
                fields=['product_id', 'move_id.invoice_date:month', 'quantity:sum', 'price_subtotal:sum'],
                groupby=['product_id',],
            )
        #venta_producto_mapping = {move['product_id'][0]: move['quantity'] for move in venta_producto}
        venta['quantity'] = venta_producto[0]['quantity'] if len(venta_producto)>0 and 'quantity'in venta_producto[0] else 0
        venta['price'] = venta_producto[0]['price_subtotal'] if len(venta_producto)>0 and 'price_subtotal'in venta_producto[0] else 0
        return venta

    def calcular(self):
        self.order_line.unlink()
        dominio = []
        dominio = [('id','in',(404,437))]
        productos = self.env['product.product'].search(dominio)
        for producto in productos:
            
            fecha_actual = self.date_start
            
            while fecha_actual <= self.date_end:
                
                ultimo_dia_mes = fecha_actual + relativedelta(day=1, months=+1, days=-1)
                primer_dia_mes = fecha_actual
                venta = self.ventas_product(producto.id, primer_dia_mes, ultimo_dia_mes)
                detalle = {
                    'product_id': producto.id,
                    'name': producto.name,
                    'order_id': self.id, 
                    'date_start': primer_dia_mes,
                    'date_end': ultimo_dia_mes,
                    'product_qty': venta['quantity'],
                    'price_unit': venta['price'],
                }
                self.env['presupuesto.venta.line'].create(detalle)

                fecha_actual += datetime.timedelta(days=32)
                fecha_actual = fecha_actual.replace(day=1)
    
    def excel(self):
        f = io.BytesIO()
        workbook = xlsxwriter.Workbook(f)
        formato_fecha = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        sheet_libro = workbook.add_worksheet('Detalle')

        i = 0;
        sheet_libro.set_column(0,30,12)
        sheet_libro.write(i,0,"Marca")
        sheet_libro.write(i,1,"Categoria")
        sheet_libro.write(i,2,"Producto")
        
        venta_producto = self.env['presupuesto.venta.line'].read_group(
                domain=[('order_id', '=', self.id),],
                fields=['product_id', 'product_qty:sum'],
                groupby=['product_id',],
            )
        productos_count_mapping = dict((g['product_id'][0], g['product_qty']) for g in venta_producto)
        
        for linea_producto in productos_count_mapping:
            i += 1
            product_id = self.env['product.product'].browse(linea_producto)
            sheet_libro.write(i,0, product_id.marca)
            sheet_libro.write(i,1, product_id.categ_id.name)
            sheet_libro.write(i,2, product_id.display_name)
            
            venta_producto_mes = self.env['presupuesto.venta.line'].read_group(
                domain=[('order_id', '=', self.id),('product_id','=',linea_producto)],
                fields=['date_start', 'product_qty:sum', 'price_unit:sum'],
                groupby=['date_start:month'],
            )
            j=2
            inicio_colunas = False
            precio_total_venta = 0
            cantidad_suma_columna = []
            for dato in venta_producto_mes:
                j += 1
                sheet_libro.write(0,j, dato['date_start:month'])
                sheet_libro.write(i,j, dato['product_qty'])
                cantidad_suma_columna.append(j)
                j += 1
                sheet_libro.write(0,j, 'Precio ' + dato['date_start:month'])
                precio_unitario =  dato['price_unit'] / dato['product_qty'] if dato['product_qty'] != 0 else 0
                sheet_libro.write(i,j, precio_unitario)
                precio_total_venta += dato['price_unit']
                if not inicio_colunas:
                    inicio_colunas = j
            
            formula_suma_columna = ''
            for coluna_suma in cantidad_suma_columna:
                columna_letra = xl_col_to_name(coluna_suma)
                formula_suma_columna += columna_letra + str(i+1) + '+'
            
            
            
  
            j += 1
            formula = '=' + formula_suma_columna[0:len(formula_suma_columna)-1]
            print(formula)
            sheet_libro.write(0,j,'Sub-Total')
            sheet_libro.write_formula(i,j,formula)
            j += 1
            sheet_libro.write(0,j, 'Venta Total Sin IVA')
            sheet_libro.write(i,j, precio_total_venta)
            j += 1
            sheet_libro.write(0,j, 'Precio Promedio Sin IVA')
            formula = '={0}{1}/{2}{3}'.format(xl_col_to_name(j-1), i+1, xl_col_to_name(j-2), i+1)
            sheet_libro.write_formula(i,j, formula)

            
            
                
        
        
        
        workbook.close()
        datos = base64.b64encode(f.getvalue())
        self.write({'archivo':datos, })
        
        return {
            'name': 'FEC',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=presupuesto.venta&id=" + str(self.id) + "&filename_field=filename&field=archivo&download=true&filename=" + 'Presupuesto_venta',
            'target': 'self',
        }


class PresupuestoVentaLine(models.Model):
    _name = 'presupuesto.venta.line'
    _description = 'Presupuesto Venta Line'
    _order = 'order_id, sequence, id'

    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)], change_default=True)
    product_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure', required=True)
    price_unit = fields.Float(string='Precio Unid.', required=True, digits='Product Price')
    
    order_id = fields.Many2one('presupuesto.venta', string='Order Reference', index=True, required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='order_id.company_id', string='Company', store=True, readonly=True)
    state = fields.Selection(related='order_id.state', store=True)
    
    date_start = fields.Date(string='Fecha Inicio',)
    date_end = fields.Date(string='Fecha Fin',)
    
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")