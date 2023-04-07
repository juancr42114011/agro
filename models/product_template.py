# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    registro_sanitario = fields.Char(string="Registro Sanitario")

class ProductCategory(models.Model):
    _inherit = "product.category"
    
    analytic_account_id = fields.Many2one('account.analytic.account', string='Cuenta Analitica',
        index=True, store=True, readonly=False, company_dependent=True, copy=True)
    
