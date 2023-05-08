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
    

class ProductCategory(models.Model):
    _inherit = "product.category"
    
    analytic_account_id = fields.Many2one('account.analytic.account', string='Cuenta Analitica',
        index=True, store=True, readonly=False, company_dependent=True, copy=True)
    
