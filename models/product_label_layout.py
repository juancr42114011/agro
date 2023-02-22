# -*- coding: utf-8 -*-

from collections import defaultdict
from odoo import fields, models
import logging


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'
    description = 'Choose the sheet layout to print the labels'

    print_format = fields.Selection(selection_add=[
    ('label_alnu_3_2', '3 x 2 Alimentos Nutricionales'),
    ], ondelete={'label_alnu_3_2': 'set default'})

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        
        dicc_products_price = {}
        dicc_products = {}
        dicc_products_lines = {}

        if self.print_format == 'label_alnu_3_2':
            xml_id = 'agro.action_report_product_ali_nutri_label_01'
            if self.move_line_ids:
                logging.warning('1 with price----------')
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
                        'cantidad': linea.qty_done,
                        'uom': linea.product_uom_id.name,
                        'lote': linea.lot_id.display_name,
                        'consumir_antes_de': linea.lot_id.use_date,
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

        logging.warning('JC-----------Return')
        logging.warning(data['dicc_products_price'])
        logging.warning(data['dicc_products'])
        logging.warning(data['dicc_products_lines'])
        logging.warning(xml_id)

        return xml_id, data