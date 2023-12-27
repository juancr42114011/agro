# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ProductCategory(models.Model):
    _inherit = "product.category"
    
    #Funcion para buscar si el producto pertenece a una categoria en especifica.
    def verificarCategoria(self, categ):

        res = self.get_external_id()
        if res.get(self.id) == categ:
            return True
        
        if self.parent_id:
            return self.parent_id.verificarCategoria(categ)
        
        return False
        
class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    def _create_invoices(self, grouped=False, final=False, date=None):
        invoice = super(SaleOrder, self)._create_invoices()
        invoice.set_diario_metodopago()
        return invoice

    def _action_confirm(self):
        #Vamos a validar que todos los productos pertenezcan a la misma categoria o categoria padre
        validando_alimentos = {}
        for line in self.order_line:
            categoria = line.product_id.categ_id
            validando_alimentos[line.id] = categoria.verificarCategoria('agro.producto_categoria_1')
        
        contador_verdadero = 0
        contador_falso = 0
        for key in validando_alimentos.keys():
            if validando_alimentos[key]:
                contador_verdadero += 1
            else:
                contador_falso += 1
        
        if contador_verdadero > 0 and contador_falso > 0:
            raise UserError(_('No se pueden mezclar productos de lineas diferentes de categoria.'))  
               
        return super(SaleOrder, self)._action_confirm()
        
class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _get_default_company2(self):
        print("----------------- si logro llegar")
        return None
    
    #company_id = fields.Many2one(default=_get_default_company2)