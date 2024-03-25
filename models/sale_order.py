# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    def action_confirm(self):
        for sale in self:
            #Se agrega esta validacion, si la empresa es (Ganadería el Manantial, S. A.), entonces no se
            #valida la existencia, porque no tiene, despues me indica Julissa que cargaran existencia.
            if self.company_id.id == 26:
                continue
            product_zero = False
            list_product = []
            if sale.order_line:
                for line in sale.order_line:
                    if line.product_id.detailed_type =='product' and line.qty_available_today < line.product_uom_qty:
                        product_zero = True
                        list_product.append(line.product_id.name)

            if product_zero and len(list_product) > 0:
                raise UserError(_(
                    'Productos sin existencia: ' + ','.join(list_product) ))

            if self.env.user.has_group('base.group_erp_manager') == False:
                margen_venta = self.env['ir.config_parameter'].sudo().get_param('sale.margen_venta')
                if float(margen_venta) > 0:
                    self.sale_price_verify(sale,float(margen_venta))
                    
        #Comienza el verdadero condi del action_confirm  
        if self._get_forbidden_state_confirm() & set(self.mapped('state')):
            raise UserError(_(
                'It is not allowed to confirm an order in the following states: %s'
            ) % (', '.join(self._get_forbidden_state_confirm())))

        for order in self.filtered(lambda order: order.partner_id not in order.message_partner_ids):
            order.message_subscribe([order.partner_id.id])
        self.write(self._prepare_confirmation_values())

        # Context key 'default_name' is sometimes propagated up to here.
        # We don't need it and it creates issues in the creation of linked records.
        context = self._context.copy()
        context.pop('default_name', None)

        self.with_context(context)._action_confirm()
        if self.env.user.has_group('sale.group_auto_done_setting'):
            self.action_done()
        return True
