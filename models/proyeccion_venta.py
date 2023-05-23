# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

from datetime import timedelta, datetime, date
from dateutil.relativedelta import relativedelta

from odoo.tools.misc import xlsxwriter
from xlsxwriter.utility import xl_col_to_name
import base64
import io
import logging

class ProyeccionVenta(models.Model):
    _name = "proyeccion.venta"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Proyeccion de Venta"
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
    year = fields.Selection(
        [(str(x), str(x)) for x in range(2020, date.today().year + 3)],
        string='Año',
        default=str(date.today().year),
        states={'draft': [('readonly', False)]},
    )
    state = fields.Selection(selection=[
            ('draft', 'Draft'),
            ('done', 'Confirmado'),
            ('cancel', 'Cancelled'),
        ], string='Status', required=True, readonly=True, copy=False, tracking=True,
        default='draft')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, states=READONLY_STATES, default=lambda self: self.env.company.id)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, states=READONLY_STATES,
        default=lambda self: self.env.company.currency_id.id)
    order_line = fields.One2many('proyeccion.venta.line', 'order_id', string='Order Lines', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)
    user_id = fields.Many2one(
        'res.users', string='Usuario', index=True, tracking=True,
        default=lambda self: self.env.user, check_company=True)
    a_presupuestar = fields.Boolean(string="A Prespuestar", help="A presupuetar.")
    archivo = fields.Binary('Archivo')
    
    @api.model
    def create(self, vals):
        company_id = vals.get('company_id', self.default_get(['company_id'])['company_id'])
        self_comp = self.with_company(company_id)
        if vals.get('name', 'New') == 'New':
            seq_date = None
            if 'date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date']))
            vals['name'] = self_comp.env['ir.sequence'].next_by_code('proyeccion.venta', sequence_date=seq_date) or '/'
        
        res = super(ProyeccionVenta, self_comp).create(vals)
        return res
    
    def buscar_ventas_product(self, product_id, date_start, date_end):
        dominio = [
            ('product_id', '=', product_id),
            ('move_id.invoice_date','>=',date_start),
            ('move_id.invoice_date','<=',date_end),
            ('move_id.journal_id.type','=','sale'),
            ('move_id.state','=','posted'),
        ]
        venta_producto = self.env['account.move.line'].search(dominio)
        return venta_producto

    def ventas_product(self, product_id, date_start, date_end):
        venta = {}
        venta_producto = self.buscar_ventas_product(product_id, date_start, date_end)
        venta['quantity'] = 0
        venta['price'] = 0
        venta['tipo'] = None
        for linea in venta_producto:
            #Si es una nota de credito se multiplica -1 en cantidad y precio.
            venta['quantity'] += linea.quantity * (-1 if linea.move_id.move_type == 'out_refund' else 1)
            venta['price'] += linea.price_subtotal * (-1 if linea.move_id.move_type == 'out_refund' else 1) 
            #Variable tipo me ayuda a identificar si el datos es el año en curso o del año pasado, Actual año en curso
            venta['tipo'] = 'Actual'
        
        if not venta_producto and self.a_presupuestar and (date_start.month >= date.today().month):
            date_start_r = date_start.replace(year=date_start.year-1)
            date_end_r = date_end.replace(year=date_end.year-1)
            venta_producto = self.buscar_ventas_product(product_id, date_start_r, date_end_r)
            for linea in venta_producto:
                #Si es una nota de credito se multiplica -1 en cantidad y precio.
                venta['quantity'] += linea.quantity * (-1 if linea.move_id.move_type == 'out_refund' else 1)
                venta['price'] += linea.price_subtotal * (-1 if linea.move_id.move_type == 'out_refund' else 1)            
            
            
            
            venta['tipo'] = 'Pasado'
        return venta

    def calcular(self):
        self.order_line.unlink()
        dominio = []
        #dominio = [('id','in',(4,585,406,404,437))]
        #dominio = [('id','in',(469,))]
        dominio = [('detailed_type','in',('product',))]
        #dominio += [('id','in',(469,))]
        productos = self.env['product.product'].search(dominio)
        self.date_start = datetime(year=int(self.year), month=1, day=1).date()
        self.date_end = datetime(year=int(self.year), month=12, day=31).date()
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
                    'tipo': venta['tipo'],
                }
                self.env['proyeccion.venta.line'].create(detalle)

                fecha_actual += timedelta(days=32)
                fecha_actual = fecha_actual.replace(day=1)
    
    def excel(self):
        f = io.BytesIO()
        workbook = xlsxwriter.Workbook(f)
        formato_fecha = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        formato_miles_decimal = workbook.add_format({'num_format': '#,##0.00'})
        sheet_libro = workbook.add_worksheet('Detalle')

        i = 0
        sheet_libro.set_column(0,0,10)
        sheet_libro.set_column(1,1,10)
        sheet_libro.set_column(2,2,30)
        sheet_libro.set_column(28,28,20)
        sheet_libro.set_column(29,29,20)
        sheet_libro.write(i,0,self.year)
        i += 1
        sheet_libro.write(i,0,"Marca")
        sheet_libro.write(i,1,"Categoria")
        sheet_libro.write(i,2,"Producto")
        
        venta_producto = self.env['proyeccion.venta.line'].read_group(
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
            
            venta_producto_mes = self.env['proyeccion.venta.line'].read_group(
                domain=[('order_id', '=', self.id),('product_id','=',linea_producto)],
                fields=['date_start', 'product_qty:sum', 'price_unit:sum'],
                groupby=['date_start'],
            )
            j=2
            inicio_colunas = False
            precio_total_venta = 0
            cantidad_suma_columna = []
            for dato in venta_producto_mes:
                j += 1
                titulo_mes = dato['date_start'][0:len(dato['date_start'])-5].capitalize()
                sheet_libro.write(0,j, titulo_mes)
                sheet_libro.write(1,j, 'Cant.')
                sheet_libro.write(i,j, dato['product_qty'])
                cantidad_suma_columna.append(j)
                j += 1
                sheet_libro.write(1,j, 'Precio')
                precio_unitario =  dato['price_unit'] / dato['product_qty'] if dato['product_qty'] != 0 else 0
                
                #sheet_libro.write(i,j, precio_unitario)
                
                precio_total_venta += dato['price_unit']
                
                formula = '={0}{1}*{2}{3}'.format(xl_col_to_name(j-1), i+1, 'AD', i+1)
                sheet_libro.write_formula(i,j, formula, formato_miles_decimal)
                
                if not inicio_colunas:
                    inicio_colunas = j
            
            formula_suma_columna = ''
            for coluna_suma in cantidad_suma_columna:
                columna_letra = xl_col_to_name(coluna_suma)
                formula_suma_columna += columna_letra + str(i+1) + '+'
            
            
            
  
            j += 1
            formula = '=' + formula_suma_columna[0:len(formula_suma_columna)-1]

            sheet_libro.write(1,j,'Sub-Total')
            sheet_libro.write_formula(i,j,formula)
            j += 1
            sheet_libro.write(1,j, 'Venta Total Sin IVA')
            sheet_libro.write(i,j, precio_total_venta, formato_miles_decimal)
            j += 1
            sheet_libro.write(1,j, 'Precio Promedio Sin IVA')
            formula = '=IFERROR({0}{1}/{2}{3},0)'.format(xl_col_to_name(j-1), i+1, xl_col_to_name(j-2), i+1)
            sheet_libro.write_formula(i,j, formula, formato_miles_decimal)

            
            
                
        
        
        
        workbook.close()
        datos = base64.b64encode(f.getvalue())
        self.write({'archivo':datos, })
        
        return {
            'name': 'FEC',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=proyeccion.venta&id=" + str(self.id) + "&filename_field=filename&field=archivo&download=true&filename=" + 'proyeccion_venta',
            'target': 'self',
        }
        
    def action_done(self):
        return self.write({'state': 'done'})
    
    def action_cancel(self):
        return self.write({'state': 'cancel'})
    
    def action_draft(self):
        return self.write({'state': 'draft'})


class ProyeccionVentaLine(models.Model):
    _name = 'proyeccion.venta.line'
    _description = 'proyeccion Venta Line'
    _order = 'order_id, sequence, id'

    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)], change_default=True)
    product_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure', required=True)
    price_unit = fields.Float(string='Precio Unid.', required=True, digits='Product Price')
    tipo = fields.Char(string='Tipo', readonly=True)
    
    order_id = fields.Many2one('proyeccion.venta', string='Order Reference', index=True, required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='order_id.company_id', string='Company', store=True, readonly=True)
    state = fields.Selection(related='order_id.state', store=True)
    
    date_start = fields.Date(string='Fecha Inicio',)
    date_end = fields.Date(string='Fecha Fin',)
    
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")