# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date, formatLang
from odoo import tools

from collections import defaultdict
from itertools import groupby
import json

import datetime
from dateutil.relativedelta import relativedelta

from odoo.tools.misc import xlsxwriter
from xlsxwriter.utility import xl_col_to_name
import base64
import io
import logging

class PurchaseOrderProyeccionWizard(models.TransientModel):
    _name = 'purchase.order.proyeccion.wizard'
    _description = 'Orden de Compra proyeccion Wizard'
    
    def _get_default_company(self):
        if not self._context.get('active_model'):
            return
        orders = self.env[self._context['active_model']].browse(self._context['active_ids'])
        return orders and orders[0].company_id.id
    
    company_id = fields.Many2one('res.company', default=_get_default_company)
    date_start = fields.Date(string='Inicio', required=True, default=lambda self: (fields.Date.context_today(self) - datetime.timedelta(days=365)).replace(day=1))
    date_end = fields.Date(string='Fin', required=True, default=lambda self: fields.Date.context_today(self))
    proyeccion_venta_id = fields.Many2one('proyeccion.venta')
    
    archivo = fields.Binary('Archivo', filters='.xls')

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
        return venta
    
    def generar_excel(self):
        f = io.BytesIO()
        workbook = xlsxwriter.Workbook(f)
        formato_fecha = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        formato_miles = workbook.add_format({'num_format': '#,##0'})
        formato_miles_decimal = workbook.add_format({'num_format': '#,##0.00'})
        
        
        orders = self.env[self._context['active_model']].browse(self._context['active_ids'])
        orden_compra = orders[0]
        
        for order in orden_compra.order_line:
            sheet_libro = workbook.add_worksheet(order.product_id.default_code)
            i = 0;
            sheet_libro.set_column(1,30,15)
            sheet_libro.set_column(0,0,20)
            sheet_libro.write(i,0,"Código de Producto")
            sheet_libro.write(i,1,order.product_id.default_code)
            sheet_libro.write(i,2,order.product_id.name)
            i += 2
            sheet_libro.write(i,0,"Ventas del Producto")
            
            fecha_actual = self.date_start
            while fecha_actual <= self.date_end:
                
                i += 1
                ultimo_dia_mes = fecha_actual + relativedelta(day=1, months=+1, days=-1)
                primer_dia_mes = fecha_actual
                venta = self.ventas_product(order.product_id.id, primer_dia_mes, ultimo_dia_mes)
                
             
                
                mes = primer_dia_mes.strftime('%B')
                anio = primer_dia_mes.strftime('%Y')
                

                sheet_libro.write(i,0,anio)
                sheet_libro.write(i,1,mes)
                sheet_libro.write(i,2,venta['quantity'],formato_miles)
                sheet_libro.write(i,3,venta['price'],formato_miles_decimal)
                
                fecha_actual += datetime.timedelta(days=32)
                fecha_actual = fecha_actual.replace(day=1)
            
            i += 3
            sheet_libro.write(i,0,"Unidades Minimas en Inventario")
            sheet_libro.write(i,1, order.product_id.cantidad_min_inventario)
            i += 1
            sheet_libro.write(i,0,"Unidad de Compra Minima")
            sheet_libro.write(i,1, order.product_id.cantidad_min_compra)
            i += 1
            sheet_libro.write(i,0,"Esta Compra")
            sheet_libro.write(i,1, order.product_qty)
            i += 1
            sheet_libro.write(i,0,"Inventario Actual")
            inventario_actual = order.product_id.qty_available
            sheet_libro.write(i,1, inventario_actual)
            
            i += 3
            sheet_libro.write(i,0,"proyeccion")
            
            i += 1
            sheet_libro.write(i,0,"Fecha")
            sheet_libro.write(i,1,"Unidades de Venta Proyectadas")
            sheet_libro.write(i,2,"Entradas")
            sheet_libro.write(i,3,"Saldo")
            sheet_libro.write(i,4,"Observaciones")
            
            for proyeccion in self.proyeccion_venta_id.order_line.filtered(lambda r: r.product_id.id == order.product_id.id):
                i += 1
                columna_saldo = 0
                sheet_libro.write(i,0,proyeccion.date_start,formato_fecha)
                sheet_libro.write(i,1,proyeccion.product_qty,formato_miles)
                
                #Voy a buscar la cantidad que se va a comprar por compra de la columna Entradas
                orden_compra_linea = self.env['purchase.order.line'].read_group(
                domain=[('product_id','=',order.product_id.id),('order_id.date_order','>=',proyeccion.date_start),('order_id.date_order','<=',proyeccion.date_end)],
                fields=['product_id', 'order_id.date_order:month', 'product_qty:sum'],
                groupby=['product_id',],
                )
                entrada = 0
                if orden_compra_linea:
                    if 'product_qty' in orden_compra_linea[0]:
                        entrada = orden_compra_linea[0]['product_qty']
                sheet_libro.write(i,2,entrada,formato_miles)
                
                #Calculo de la columna Saldo
                columna_saldo = inventario_actual - proyeccion.product_qty + entrada
                sheet_libro.write(i,3,columna_saldo,formato_miles)
                inventario_actual = columna_saldo
            
            if order.product_id.image_1920 != False:
                i += 3
                image = tools.ImageProcess(order.product_id.image_1920)
                # Redimiensionar imagen 250 X 250
                resize_image = image.resize(250, 250)    
                resize_image_b64 = resize_image.image_base64()   
                nueva_imagen = resize_image_b64      
                
                if nueva_imagen:
                    product_image = io.BytesIO(base64.b64decode(nueva_imagen))
                    sheet_libro.insert_image(1, 5, "image.png", {
                        'x_offset':        5,
                        'y_offset':        5,
                        'x_scale':         2,
                        'y_scale':         2,
                        'object_position': 2,
                        'image_data':      product_image,
                        'url':             None,
                        'description':     None,
                        'decorative':      False,
                    })
            
            

            
        
        
        
        workbook.close()
        datos = base64.b64encode(f.getvalue())
        self.write({'archivo':datos, })
        
        return {
            'name': 'FEC',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=purchase.order.proyeccion.wizard&id=" + str(self.id) + "&filename_field=filename&field=archivo&download=true&filename=" + 'AnalisisCompra',
            'target': 'self',
        }