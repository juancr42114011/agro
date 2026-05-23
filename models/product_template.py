# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    registro_sanitario = fields.Char(string="Registro Sanitario")
    cantidad_min_inventario = fields.Float(
        'Cantidades Minima en Inventario', default=0,
        help="Cantidades Minima en Inventario")
    cantidad_min_compra = fields.Float(
        'Cantidad de Compra Minima', default=0,
        help="Cantidad de Compra Minima")
    a_presupuestar = fields.Boolean(default=True, help="Bandera que nos indica si se incluye en el presupuesto.")
    codigo_referencia = fields.Char(
        string='Código de Referencia',
        index=True,
        copy=False,
        help='Código de referencia interno del producto (columna Código del Kardex)',
    )
    

class ProductCategory(models.Model):
    _inherit = "product.category"
    
    analytic_account_id = fields.Many2one('account.analytic.account', string='Cuenta Analitica',
        index=True, store=True, readonly=False, company_dependent=True, copy=True)
    
