# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        self._check_internal_transfer_availability()
        return super(StockPicking, self).button_validate()

    def _check_internal_transfer_availability(self):
        for picking in self:
            if picking.location_id.usage != 'internal' or picking.location_dest_id.usage != 'internal':
                continue

            needed_qty_by_product = {}
            for move in picking.move_lines.filtered(lambda m: m.state not in ('done', 'cancel')):
                qty = move.quantity_done or move.product_uom_qty
                if not qty:
                    continue
                qty_in_uom = move.product_uom._compute_quantity(qty, move.product_id.uom_id)
                needed_qty_by_product[move.product_id] = needed_qty_by_product.get(move.product_id, 0.0) + qty_in_uom

            for product, needed_qty in needed_qty_by_product.items():
                available_qty = product.with_context(location=picking.location_id.id).qty_available
                if float_compare(available_qty, needed_qty, precision_rounding=product.uom_id.rounding) < 0:
                    raise UserError(_(
                        'No hay suficiente existencia del producto "%(product)s" en la ubicación de origen '
                        '"%(location)s" para realizar la transferencia.\n'
                        'Disponible: %(available)s %(uom)s\n'
                        'Requerido: %(needed)s %(uom)s'
                    ) % {
                        'product': product.display_name,
                        'location': picking.location_id.display_name,
                        'available': available_qty,
                        'needed': needed_qty,
                        'uom': product.uom_id.name,
                    })
