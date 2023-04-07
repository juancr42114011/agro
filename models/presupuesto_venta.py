# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

class PresupuestoVenta(models.Model):
    _name = "presupuesto.venta"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Presupuesto de Venta"
    _order = 'id desc'
    _mail_post_access = 'read'
    _check_company_auto = True
    
    name = fields.Char(string='Number', 
                       copy=False, 
                       readonly=True, 
                       store=True, 
                       index=True,
                       )
    date = fields.Date(
        string='Date',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        copy=False,
        tracking=True,
        default=fields.Date.context_today
    )
    state = fields.Selection(selection=[
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('cancel', 'Cancelled'),
        ], string='Status', required=True, readonly=True, copy=False, tracking=True,
        default='draft')
    company_id = fields.Many2one(comodel_name='res.company', string='Company',
                                 store=True, readonly=True,
                                 compute='_compute_company_id')
    
    @api.model
    def create(self, vals):
        company_id = vals.get('company_id', self.default_get(['company_id'])['company_id'])
        self_comp = self.with_company(company_id)
        if vals.get('name', 'New') == 'New':
            seq_date = None
            if 'date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date']))
            vals['name'] = self_comp.env['ir.sequence'].next_by_code('presupuesto.venta', sequence_date=seq_date) or '/'
        
        res = super(PresupuestoVenta, self_comp).create(vals)
        return res

    def _compute_company_id(self):
        for move in self:
            move.company_id = move.journal_id.company_id or move.company_id or self.env.company