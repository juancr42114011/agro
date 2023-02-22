# -*- coding: utf-8 -*-

from odoo import models, fields, api

from functools import lru_cache
import logging


class ReporteEtiquetaSinPrecio (models.AbstractModel):
    _name='report.agro.etiqueta_ali_nu_3_x_2_01'
    _description='Eriquetas 3x2 Alimentos Nutricionales'

    def creacion_datos(self, orders):
        dicc_products={}
        for order in orders:
            for linea in order.order_line:
                if linea.product_id.default_code not in dicc_products:
                    dicc_products[linea.product_id.default_code]=[]
                for i in range(int(linea.product_uom_qty)):
                    if linea.product_id.default_code in dicc_products:
                        dicc_products[linea.product_id.default_code].append({
                        'codigo':linea.product_id.default_code,
                        'descripcion': linea.product_id.name,
                        'codigo_barras': linea.product_id.barcode
                        })
        return dicc_products

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['sale.order'].browse(docids)
        dicc_products = self.creacion_datos(docs)
        return {
            'doc_ids': docids,
            'doc_model': 'sale.order',
            'docs': docs,
            'dicc_products': dicc_products,
        }
