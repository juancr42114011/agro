# -*- coding: utf-8 -*-

from odoo import api, fields, models

class AccountMove(models.Model):
    _inherit = "account.move"
    
    def set_diario_metodopago(self):
        for record in self:
            if record.company_id.id == 1: #La empresa es Importaciones Generales, S. A.
                factura_credito = False
                if not record.invoice_payment_term_id or record.invoice_payment_term_id.id == self.env.ref('account.account_payment_term_immediate').id:
                    record.journal_id = 29  #Factura Contado Mobiliario y Suministros
                else:
                    record.journal_id = 96 #Factura Cambiaria
                    factura_credito = True
                
                for line in record.invoice_line_ids:
                    if line.product_id.categ_id.verificarCategoria('agro.producto_categoria_1'):
                        if factura_credito:
                            record.journal_id = self.env.ref('agro.sale_fa_ve_al_nu_ca').id
                        else:
                            record.journal_id = self.env.ref('agro.sale_fa_ve_al_nu_co').id
                        continue

    @api.onchange('invoice_payment_term_id')
    def _onchange_invoice_payment_term_id(self):
        self.set_diario_metodopago()

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.depends('product_id', 'account_id', 'partner_id', 'date')
    def _compute_analytic_tag_ids(self):
        for record in self:
            if not record.exclude_from_invoice_tab or not record.move_id.is_invoice(include_receipts=True):
                rec = self.env['account.analytic.default'].account_get(
                    product_id=record.product_id.id,
                    partner_id=record.partner_id.commercial_partner_id.id or record.move_id.partner_id.commercial_partner_id.id,
                    account_id=record.account_id.id,
                    user_id=record.env.uid,
                    date=record.date,
                    company_id=record.move_id.company_id.id
                )
                if rec:
                    record.analytic_tag_ids = rec.analytic_tag_ids
                    
            if not record.analytic_account_id and record.product_id:
                record.analytic_account_id = record.product_id.categ_id.analytic_account_id.id


