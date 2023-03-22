# -*- coding: utf-8 -*-

from collections import defaultdict
from odoo import fields, models
import logging


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'
    description = 'Choose the sheet layout to print the labels'

    print_format = fields.Selection(selection_add=[
    ('label_alnu_3_2', '3 x 2 Alimentos Nutricionales 01'),
    ], ondelete={'label_alnu_3_2': 'set default'})

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        
        dicc_products_price = {}
        dicc_products = {}
        dicc_products_lines = {}


        if self.print_format == 'label_alnu_3_2':
            xml_id = 'agro.action_report_product_ali_nutri_label_01'
            #Sirve cuando si imprime desde la opcion de Productos /   Lotes
            if self.move_line_ids:
                for linea in self.move_line_ids:
                    
                    print(linea)
                    if linea.product_id.id not in dicc_products_price:
                        dicc_products_price[linea.product_id.id]=[]

                    if linea.product_id.id in dicc_products_price:
                        dicc_products_price[linea.product_id.id].append({
                        'codigo':linea.product_id.default_code,
                        'descripcion': linea.product_id.name,
                        'precio':linea.product_id.list_price,
                        'codigo_barras': linea.product_id.barcode,
                        'cantidad': linea.product_uom_qty,
                        'uom': linea.product_uom_id.name,
                        'lote': linea.lot_id.display_name,
                        'consumir_antes_de': linea.lot_id.use_date,
                        'registro_sanitario': linea.product_id.registro_sanitario,
                        })
            #Sirve cuando se imprime desde la opcion de Productos 
            if self.product_tmpl_ids:
                for i in range(self.custom_quantity):
                    if self.product_tmpl_ids.default_code not in dicc_products:
                        dicc_products[self.product_tmpl_ids.default_code]=[]

                    if self.product_tmpl_ids.default_code in dicc_products:
                        dicc_products[self.product_tmpl_ids.default_code].append({
                        'codigo':self.product_tmpl_ids.default_code,
                        'descripcion': self.product_tmpl_ids.name,
                        'codigo_barras': self.product_tmpl_ids.barcode,
                        'uom': self.product_tmpl_ids.uom_id.name,
                        'precio': self.product_tmpl_ids.list_price,
                        'cantidad': False,
                        'lote': False,
                        'consumir_antes_de': False,
                        'registro_sanitario': self.product_tmpl_ids.registro_sanitario,
                        })

            new_value = None
            if dicc_products_price:
                new_value = dicc_products_price.values()
            if dicc_products:
                new_value = dicc_products.values()

            nueva_list_precios = []
            if new_value:
                for n in new_value:
                    nueva_list_precios.append(n)
                            
            data['dicc_products_price']=nueva_list_precios
            data['dicc_products']=nueva_list_precios
            data['dicc_products_lines']=dicc_products_lines

        return xml_id, data