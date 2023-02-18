# -*- coding: utf-8 -*-

from odoo import models, fields, api


class agro(models.Model):
    _name = 'agro.agro'
    _description = 'agro.agro'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"
    
    def create_invoices(self):
        rst = super(SaleAdvancePaymentInv, self).create_invoices()
        print("Hola mundo")
        return rst
    
    def _create_invoice(self, order, so_line, amount):
        print("--------------------------------------------------------")
        invoice = super(SaleAdvancePaymentInv, self)._create_invoice()
        print(invoice)
        return invoice

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    def _create_invoices(self, grouped=False, final=False, date=None):
        invoice = super(SaleOrder, self)._create_invoices()
        print(invoice)
        for line in invoice.invoice_line_ids:
            if line.product_id.categ_id == self.env.ref("agro.producto_categoria_1"):
                invoice.journal_id = self.env.ref('agro.sale_fa_ve_al_nu_co')
        return invoice