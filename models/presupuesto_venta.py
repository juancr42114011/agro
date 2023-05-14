# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

import datetime
from dateutil.relativedelta import relativedelta

from odoo.tools.misc import xlsxwriter
from xlsxwriter.utility import xl_col_to_name
import base64
import io
import logging

class PresupuestoVenta(models.Model):
    _name = "presupuesto.venta"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Presupuesto de Venta"
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


class PresupuestoVentaLine(models.Model):
    _name = 'presupuesto.venta.line'
    _description = 'Presupuesto Venta Line'
    _order = 'order_id, sequence, id'

    name = fields.Text(string='Description', required=True)
