# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    guia_ganado = fields.Char(string='Guia Ganado', help="Guia especial de despacho de ganado", tracking=True)
    
    def _validar_confirmacion(self):
        # Reemplaza la validación de imporgesa (no llama a super)
        for sale in self:
            #Se agrega esta validacion, si la empresa es (Ganadería el Manantial, S. A.), entonces no se
            #valida la existencia, porque no tiene, despues me indica Julissa que cargaran existencia.
            if sale.company_id.id == 26:
                continue
            product_zero = False
            list_product = []
            if sale.order_line:
                for line in sale.order_line:
                    if line.product_id.is_storable and line.qty_available_today < line.product_uom_qty:
                        product_zero = True
                        list_product.append(_(
                            '%(product)s (Disponible: %(available)s %(uom)s, Solicitado: %(requested)s %(uom)s)'
                        ) % {
                            'product': line.product_id.display_name,
                            'available': line.qty_available_today,
                            'requested': line.product_uom_qty,
                            'uom': line.product_uom_id.name,
                        })

            if product_zero and len(list_product) > 0:
                raise UserError(_(
                    'Productos sin existencia suficiente:\n' + '\n'.join(list_product) ))

            if self.env.user.has_group('base.group_erp_manager') == False:
                margen_venta = self.env['ir.config_parameter'].sudo().get_param('sale.margen_venta')
                if float(margen_venta) > 0:
                    self.sale_price_verify(sale,float(margen_venta))

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        # Restaurar valores predeterminados si fueron cambiados por el cliente
        defaults = self.env['ir.default'].with_company(self.company_id)._get_model_defaults('sale.order')
        if 'warehouse_id' in defaults:
            self.warehouse_id = defaults['warehouse_id']
        if 'user_id' in defaults:
            self.user_id = defaults['user_id']