# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

class PresupuestoVenta(models.Model):
    _name = "presupuesto.venta"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'sequence.mixin']
    _description = "Presupuesto de Venta"
    _order = 'id desc'
    _mail_post_access = 'read'
    _check_company_auto = True
    
    name = fields.Char(string='Number', copy=False, compute='_compute_name', readonly=False, store=True, index=True, tracking=True)
  