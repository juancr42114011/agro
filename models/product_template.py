# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    registro_sanitario = fields.Char(string="Registro Sanitario")