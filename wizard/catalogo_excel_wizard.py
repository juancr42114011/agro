# -*- coding: utf-8 -*-

from odoo import fields, models, _
import logging
import csv
from odoo.exceptions import UserError, ValidationError
import base64
import io


_logger = logging.getLogger(__name__)

import tempfile
import binascii
import xlrd
from datetime import datetime


class ImportarCatalogosExcelWizard(models.TransientModel):

	_name = "comelasa.importar.catalogos.excel.wizard"
	_description = "Importar Pedidos de Excel"

	archivo = fields.Binary(string="Archivo (XLS)")
	tipo_plantilla = fields.Selection([
		('p1', 'Crear productos'),
  		('p2', 'Cargar existencias'),

	], required=True, default='p1')

	ubicacion = fields.Many2one('stock.location', string='Ubicacion')
	#inventario = fields.Many2one('stock.inventory', string='Inventario')
	transferencia = fields.Many2one('stock.picking', string='Transferencia')
	counterpart_account_id = fields.Many2one(
        'account.account', string="Counter-Part Account",
        domain=[('deprecated', '=', False)])

	def cargar_catalogo_excel(self):
		if self.tipo_plantilla == 'p1':
			self._crear_productos()
		elif self.tipo_plantilla == 'p2':
			self._cargar_existencias()
   
	def _cargar_existencias(self):
		fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
		fp.write(binascii.a2b_base64(self.archivo))
		fp.seek(0)
		values = []
		workbook = xlrd.open_workbook(fp.name)
		sheet = workbook.sheet_by_index(0)
		product_template = []
		i = 0
  
		Product = self.env['product.product']
		Quant = self.env['stock.quant']

		updated = 0
		not_found = []
  
		for row_no in range(sheet.nrows):
			i+=1
			if row_no <= 0:
				fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
			else:
				row = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))

				# Columnas del archivo
				codigo_odoo = row[1]     # Código nuevo Odoo
				existencia = row[24]     # Columna ventas

				if not codigo_odoo:
					continue

				default_code = str(codigo_odoo).strip()

				# Cantidad
				qty = 0.0
				if existencia:
					qty = float(existencia)

				# =====================================
				# BUSCAR PRODUCTO
				# =====================================

				product = Product.search([
					('default_code', '=', default_code)
				], limit=1)

				if not product:
					not_found.append(default_code)
					continue

				# =====================================
				# BUSCAR QUANT
				# =====================================

				quant = Quant.search([
					('product_id', '=', product.id),
					('location_id', '=', self.ubicacion.id),
				], limit=1)

				if quant:

					# Ajustar existencia
					quant.inventory_quantity = qty
					quant.action_apply_inventory()

				else:

					quant = Quant.create({
						'product_id': product.id,
						'location_id': self.ubicacion.id,
						'inventory_quantity': qty,
					})

					quant.action_apply_inventory()

				updated += 1

			# =====================================
			# MENSAJE FINAL
			# =====================================

			message = _(
				'Productos actualizados: %s'
			) % updated

			if not_found:
				message += _(
					'\nProductos no encontrados:\n%s'
				) % '\n'.join(not_found[:20])

		return {
			'type': 'ir.actions.client',
			'tag': 'display_notification',
			'params': {
				'title': _('Carga de existencia completada'),
				'message': message,
				'sticky': True,
				'type': 'success',
			}
		}

	def _crear_productos(self):
		fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
		fp.write(binascii.a2b_base64(self.archivo))
		fp.seek(0)
		values = []
		workbook = xlrd.open_workbook(fp.name)
		sheet = workbook.sheet_by_index(0)
		product_template = []
		i = 0
		ProductTemplate = self.env['product.template']
		ProductCategory = self.env['product.category']
		Account = self.env['account.account']  
		created = 0
		updated = 0
  
		cuenta_contable_inventario = self.env['account.account'].search([('code', '=', '1-1-03-05-002')], limit=1)
		if not cuenta_contable_inventario:
			raise UserError(_("No se encontró la cuenta contable de inventario (1-1-03-05-002). Por favor, cree esta cuenta antes de continuar."))

		cuenta_contable_inventario_transito = self.env['account.account'].search([('code', '=', '1-1-03-05-001')], limit=1)
		if not cuenta_contable_inventario_transito:
			raise UserError(_("No se encontró la cuenta contable de inventario en tránsito (1-1-03-05-001). Por favor, cree esta cuenta antes de continuar."))


		for row_no in range(sheet.nrows):
			i+=1
			if row_no <= 0:
				fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
			else:
				row = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))

				# Columnas del archivo
				codigo_original = row[0]
				codigo_odoo = row[1]
				descripcion = row[2]
				cuenta_contable = row[3]
				categoria = row[7]
				subcategoria = row[8]
				subsubcategoria = row[9]
				
				costo = row[19]
    
				# Validar referencia
				if not codigo_odoo:
					continue

				default_code = str(codigo_odoo).strip()
				# Limpiar descripción
				nombre_producto = ''
				if descripcion:
					nombre_producto = str(descripcion).replace('\t', '').strip()    

				# =========================
				# CREAR / BUSCAR CATEGORIA
				# =========================


				categ_id = False

				if categoria:

					parent_category = ProductCategory.search([
						('name', '=', str(categoria).strip()),
						('parent_id', '=', False)
					], limit=1)

					if not parent_category:
						parent_category = ProductCategory.create({
							'name': str(categoria).strip(),
							'property_valuation': 'real_time',
							'property_cost_method': 'average',
							'property_stock_valuation_account_id': cuenta_contable_inventario.id,
							'property_account_expense_categ_id': cuenta_contable_inventario_transito.id,
							'property_stock_account_input_categ_id': cuenta_contable_inventario_transito.id,
							'property_stock_account_output_categ_id': 547,  # Cuenta de salida de inventario (ajustar según su configuración)
							'property_account_income_categ_id': 5868,  # Cuenta de ingresos (ajustar según su configuración)
						})

					categ_id = parent_category.id

					# Crear subcategoría
					if subcategoria:

						child_category = ProductCategory.search([
							('name', '=', str(subcategoria).strip()),
							('parent_id', '=', parent_category.id)
						], limit=1)

						if not child_category:
							child_category = ProductCategory.create({
								'name': str(subcategoria).strip(),
								'parent_id': parent_category.id,
								'property_valuation': 'real_time',
								'property_cost_method': 'average',
								'property_stock_valuation_account_id': cuenta_contable_inventario.id,
								'property_account_expense_categ_id': cuenta_contable_inventario_transito.id,
								'property_stock_account_input_categ_id': cuenta_contable_inventario_transito.id,
								'property_stock_account_output_categ_id': 547,  # Cuenta de salida de inventario (ajustar según su configuración)
								'property_account_income_categ_id': 5868,  # Cuenta de ingresos (ajustar según su configuración)        
							})

						categ_id = child_category.id
      
						# Crear sub-subcategoría
						if subsubcategoria:
    
							sub_child_category = ProductCategory.search([
								('name', '=', str(subsubcategoria).strip()),
								('parent_id', '=', child_category.id)
							], limit=1)

							if not sub_child_category:
								sub_child_category = ProductCategory.create({
									'name': str(subsubcategoria).strip(),
									'parent_id': child_category.id,
									'property_valuation': 'real_time',
									'property_cost_method': 'average',
									'property_stock_valuation_account_id': cuenta_contable_inventario.id,
									'property_account_expense_categ_id': cuenta_contable_inventario_transito.id,
									'property_stock_account_input_categ_id': cuenta_contable_inventario_transito.id,
									'property_stock_account_output_categ_id': 547,  # Cuenta de salida de inventario (ajustar según su configuración)
									'property_account_income_categ_id': 5868,  # Cuenta de ingresos (ajustar según su configuración)
								})

							categ_id = sub_child_category.id

						# =========================
						# BUSCAR CUENTA CONTABLE
						# =========================

						property_account_income_id = False

						if cuenta_contable:

							account = Account.search([
								('code', '=', str(cuenta_contable).strip())
							], limit=1)

							if account:
								property_account_income_id = account.id

						# =========================
						# VALORES DEL PRODUCTO
						# =========================

						vals = {
							'name': nombre_producto,
							'default_code': default_code,
							'type': 'product',
							'categ_id': categ_id,
							'standard_price': costo or 0.0,
							'marca': 'TAITS',
							'codigo_referencia': codigo_original,
						}

						# Asignar cuenta contable si existe
						if property_account_income_id:
							vals['property_account_income_id'] = property_account_income_id

						# =========================
						# CREAR O ACTUALIZAR
						# =========================

						product = ProductTemplate.search([
							('default_code', '=', default_code)
						], limit=1)

						if product:
							product.write(vals)
							updated += 1
						else:
							ProductTemplate.create(vals)
							created += 1

		return {
			'type': 'ir.actions.client',
			'tag': 'display_notification',
			'params': {
				'title': _('Importación completada'),
				'message': _(
					'Productos creados: %s\nProductos actualizados: %s'
				) % (created, updated),
				'sticky': False,
				'type': 'success',
			}
		}


	def _revisar_producto(self):
		fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
		fp.write(binascii.a2b_base64(self.archivo))
		fp.seek(0)
		values = []
		workbook = xlrd.open_workbook(fp.name)
		sheet = workbook.sheet_by_index(0)
		product_template = []
		i = 0

		for row_no in range(sheet.nrows):
			i+=1
			if row_no <= 0:
				fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
			else:
				line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
				producto = {}

				producto_line = {
                    "barra": line[0].strip(),
                    "empresa": line[1].strip(),
					"codigo": line[2].strip(),
					"descripcion": line[3].strip(),
					"existencia": line[4].strip(),
					"costo": float(line[5].strip()) if line[5] else 0,
					"costototal": float(line[5].strip()) if line[5] else 0,
				}

				product_product = None
				product_template = self.env["product.template"].search([('default_code','=',producto_line['codigo'])], limit=1)
				if product_template:
					product_product = None
					product_product = self.env["product.product"].search([('product_tmpl_id','=',product_template.id)])
				else:
					product_product = None
					product_template = self.env["product.template"].search([('name','=',producto_line['descripcion'])], limit=1)
					if product_template:
						product_product = self.env["product.product"].search([('product_tmpl_id','=',product_template.id)])

				encontro = False
				cargado = 'nada'
				carga_valor = 0
				if product_product:
					encontro = True

					carga = self.env["stock.move.line"].search([
							('location_id','=',14),
							('location_dest_id','=',8),
							('state','=','done'),
							('product_id','=',product_product.id)
					])
					for c in carga:
						cargado = 'cargado'
						carga_valor += c.qty_done

					descarga = self.env["stock.move.line"].search([
							('location_id','=',8),
							('location_dest_id','=',14),
							('state','=','done'),
							('product_id','=',product_product.id)
					])
					for d in descarga:
						cargado = 'cargado/descargado'
						carga_valor -= d.qty_done



				print("%s |----------%s------------------ %s" % (i,encontro,producto_line))

				with open("/mnt/extra-addons/Imporguesa/holaSI.txt", 'a') as f:
					if encontro:
						print("%s|%s|%s|%s|%s|odoo|%s|%s|%s|carga|%s|%s" % (
						i,
						producto_line['codigo'],
						producto_line['descripcion'],
						producto_line['existencia'],
						producto_line['costo'],
						product_product.product_tmpl_id.name,
						product_product.standard_price,
						product_product.qty_available,
						cargado,  #Valor true si esta en la carga inicial, y falso si no
						carga_valor,
						), file=f)

				with open("/mnt/extra-addons/Imporguesa/holaNO.txt", 'a') as g:
					if not encontro:
						print("%s|%s|%s|%s|%s" % (i,producto_line['codigo'],producto_line['descripcion'],producto_line['existencia'],producto_line['costo']), file=g)



	def _actualizar_costos(self):
		fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
		fp.write(binascii.a2b_base64(self.archivo))
		fp.seek(0)
		values = []
		workbook = xlrd.open_workbook(fp.name)
		sheet = workbook.sheet_by_index(0)
		product_template = []
		i = 2

		for row_no in range(sheet.nrows):
			if row_no <= 0:
				fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
			else:
				line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
				producto = {}

				producto_line = {
                    "codigo1": line[0].strip(),
                    "codigo2": line[1].strip(),
					"codigo3": line[2].strip(),
					"descripcion": line[3].strip(),
					"existencia": line[4].strip(),
					"costo": float(line[5].strip()) if line[5] else 0,
					}
				if producto_line:

					product_template = self.env["product.template"].search([('default_code','=',producto_line['codigo2'])], limit=1)
					if product_template:
						product_product = self.env["product.product"].search([('product_tmpl_id','=',product_template.id)])
					else:
						product_template = self.env["product.template"].search([('name','=',producto_line['descripcion'])], limit=1)
						if product_template:
							product_product = self.env["product.product"].search([('product_tmpl_id','=',product_template.id)])

						else:
							product_product = None
							print("%s |----------NO------------------ %s" % (i,producto_line))

					if product_product:
						costo_anterior = product_product.standard_price
						if costo_anterior != producto_line['costo']:
							product_product._change_standard_price(producto_line['costo'], counterpart_account_id=self.counterpart_account_id.id)
							costo_nuevo = product_product.standard_price
							print("%s |- [%s] (%s) Costo anterior (%s), Consto nuevo(%s), ExistenciaActual(%s), ExistenciaNueva(%s)" % (product_product.product_tmpl_id.id,product_product.default_code,producto_line['descripcion'], str(costo_anterior), str(producto_line['costo']), str(product_product.qty_available), producto_line['existencia']))
				i+=1

	# def _carga_transferencia(self):
	# 	fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
	# 	fp.write(binascii.a2b_base64(self.archivo))
	# 	fp.seek(0)
	# 	values = []
	# 	workbook = xlrd.open_workbook(fp.name)
	# 	sheet = workbook.sheet_by_index(0)
	# 	product_template = []
	# 	i = 1

	# 	for row_no in range(sheet.nrows):
	# 		if row_no <= 0:
	# 			fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
	# 		else:
	# 			line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
	# 			producto = {}

	# 			producto_line = {
    #                 "referencia_interna": line[0].strip(),
    #                 "nombre": line[2].strip(),
	# 				"cantidad": float(line[5].strip()) if line[5] else 0.0,
	# 				}
	# 			if producto_line['cantidad'] > 0:
	# 				product = self.env["product.product"].search([('name','=',producto_line['nombre'])], limit=1)
	# 				if product:
	# 					product_line = self.env["stock.inventory.line"].search([('inventory_id','=',self.inventario.id),('product_id','=',product.id)])
	# 					if product_line:
	# 						product_line.product_qty = producto_line['cantidad']
	# 					else:
	# 						new_linea_inventario = {}
	# 						new_linea_inventario['picking_id'] = self.transferencia.id
	# 						new_linea_inventario['name'] = product.display_name
	# 						new_linea_inventario['description_picking'] = product.name
	# 						new_linea_inventario['product_id'] = product.id
	# 						new_linea_inventario['location_id'] = self.transferencia.location_id.id
	# 						new_linea_inventario['location_dest_id'] = self.transferencia.location_dest_id.id
	# 						new_linea_inventario['picking_type_id'] = self.transferencia.picking_type_id.id
	# 						#new_linea_inventario['product_qty'] = producto_line['cantidad']
	# 						new_linea_inventario['product_uom'] = 1
	# 						new_linea_inventario['product_uom_qty'] = producto_line['cantidad']
	# 						new_linea_inventario['company_id'] = self.env.user.company_id.id
	# 						self.env["stock.move"].create(new_linea_inventario)
	# 				else:
	# 					print("%s |---------------------------- %s" % (i,producto_line))
	# 				i+=1

	# def _carga_existencia(self):
	# 	fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
	# 	fp.write(binascii.a2b_base64(self.archivo))
	# 	fp.seek(0)
	# 	values = []
	# 	workbook = xlrd.open_workbook(fp.name)
	# 	sheet = workbook.sheet_by_index(0)
	# 	product_template = []
	# 	i = 1

	# 	for row_no in range(sheet.nrows):
	# 		if row_no <= 0:
	# 			fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
	# 		else:
	# 			line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
	# 			producto = {}

	# 			producto_line = {
    #                 "referencia_interna": line[0].strip(),
    #                 "nombre": line[2].strip(),
	# 				"cantidad": float(line[5].strip()) if line[5] else 0.0,
	# 				}
	# 			if producto_line['cantidad'] > 0:
	# 				product = self.env["product.template"].search([('name','=',producto_line['nombre'])], limit=1)
	# 				product = self.env["product.product"].search([('product_tmpl_id','=',product.id)], limit=1)
	# 				if product:
	# 					product_line = self.env["stock.inventory.line"].search([('inventory_id','=',self.inventario.id),('product_id','=',product.id)])
	# 					if product_line:
	# 						product_line.product_qty = producto_line['cantidad']
	# 					else:
	# 						new_linea_inventario = {}
	# 						new_linea_inventario['inventory_id'] = self.inventario.id
	# 						new_linea_inventario['product_id'] = product.id
	# 						new_linea_inventario['location_id'] = self.ubicacion.id
	# 						new_linea_inventario['product_qty'] = producto_line['cantidad']
	# 						new_linea_inventario['company_id'] = self.env.user.company_id.id
	# 						self.env["stock.inventory.line"].create(new_linea_inventario)
	# 				else:
	# 					print("%s |---------------------------- %s" % (i,producto_line))
	# 				#print("%s |---------------------------- %s" % (i,producto_line))
	# 				i+=1

	def _carga_orden_compra(self):
		fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
		fp.write(binascii.a2b_base64(self.archivo))
		fp.seek(0)
		values = []
		workbook = xlrd.open_workbook(fp.name)
		sheet = workbook.sheet_by_index(0)
		product_template = []
		i = 1
		for row_no in range(sheet.nrows):
			if row_no <= 0:
				fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
			else:
				line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
				producto = {}
				producto_line = {
                    "orden_id": line[0],
                    "producto_id": line[1].strip(),
					"descripcion": line[2].strip(),
                    "cantidad": line[3],
                    "precio": line[4],
					}
				product_id = self._find_products(producto_line['producto_id'])
				if product_id:
					producto['product_id'] = product_id.id
					producto['name'] = producto_line['descripcion']
					producto['product_qty'] = producto_line['cantidad']
					producto['product_uom'] = product_id.uom_po_id.id
					producto['price_unit'] = producto_line['precio']
					producto['date_planned'] = datetime.today()
					producto['order_id'] = int(float(producto_line['orden_id']))
					order = self.env['purchase.order.line'].create(producto)
					_logger.info("Creando producto %s codigo %s" % (i, producto_line['producto_id']))
				else:
					_logger.info("No se creo producto %s codigo %s" % (i, producto_line['producto_id']))
				i += 1

	def _find_products(self, product):
		find_codigo = self.env['product.template'].search([("default_code","=",product)], limit=1)
		return find_codigo

	def _cargar_catalogo_productos(self):
		fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
		fp.write(binascii.a2b_base64(self.archivo))
		fp.seek(0)
		values = []
		workbook = xlrd.open_workbook(fp.name)
		sheet = workbook.sheet_by_index(0)
		product_template = []
		i = 1
		for row_no in range(sheet.nrows):
			if row_no <= 0:
				fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
			else:
				line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
				producto = {}
				producto_line = {
                    "codigo": line[0].strip(),
                    "marca": line[1],
                    "name": line[3].strip(),
                    "padre": line[5],
                    "categoria": line[6],
                    "costo": line[7],
                    "precio": line[8],
                    "proveedor": line[11],
					#"dai": line[12],
					}
				producto['name'] = producto_line['name']
				producto['default_code'] = producto_line['codigo']
				producto['comelasa_product_brand_id'] = self._get_Marca(producto_line['marca']).id
				producto['type'] = 'product'
				producto['categ_id'] = self._get_Categoria(producto_line['padre'], producto_line['categoria']).id
				producto['list_price'] = producto_line['precio']
				producto['standard_price'] = producto_line['costo']
				#producto['dai_id'] = self._get_Dai(producto_line['dai'])
				product_template = self.create_products(producto, producto_line, i)
				_logger.info("Creando producto %s codigo %s" % (i, product_template["name"]))
				i += 1

	def _get_Dai(self, dai):
		dai_id = self.env['product.dai'].search([('name','=',dai)])
		if dai_id:
			return dai_id.id
		return None

	def _get_Marca(self, marca):
		brand = self.env['comelasa.product_brand'].search([('name','ilike',marca)],limit=1)
		if not brand:
			brand = self.env['comelasa.product_brand'].create({
                "name": marca
            })
		return brand

	def _get_Categoria(self, padre, categoria):
		padre_categoria = self.env['product.category'].search([('name','=',padre)], limit=1)
		if not padre_categoria:
			padre_categoria = self.env['product.category'].search([('name','=','All')])
			padre_categoria = self.env['product.category'].create({
                "name": padre,
                "parent_id": padre_categoria.id,
            })

		categoria_producto = self.env['product.category'].search([('name','=',categoria)], limit=1)
		if not categoria_producto:
			categoria_producto = self.env['product.category'].create({
                "name": categoria,
                "parent_id": padre_categoria.id,
            })

		return categoria_producto



	def create_products(self, product, producto_line, contador):
		find_codigo = self.env['product.template'].search([("default_code","=",product["default_code"])], limit=1)
		if not find_codigo:
			find_codigo = self.env['product.template'].create(product)
			supplierinfo1 = self.env['product.supplierinfo'].create({
                'product_tmpl_id': find_codigo.id,
                'name': self._get_Contacto(producto_line['proveedor']).id,
                'min_qty': 1,
                'price': product['standard_price'],
                'sequence': 1,
            })
			name = ('product_comelasa_template_%s' % str(find_codigo.id).strip())
			self.env['ir.model.data'].create({
	            'name': name,
	            'model': 'product.template',
	            'module': '__export__',
	            'res_id': find_codigo.id,
				})

		else:
			find_codigo["name"] = product["name"]
		return find_codigo

	def _get_Contacto(self, nombre):
		contacto = self.env['res.partner'].search([('name','ilike',nombre)], limit=1)
		if not contacto:
			contacto = self.env['res.partner'].create({
                "name": nombre,
            })
		return contacto


	def _asignar_origen(self):
		fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
		fp.write(binascii.a2b_base64(self.archivo))
		fp.seek(0)
		values = []
		workbook = xlrd.open_workbook(fp.name)
		sheet = workbook.sheet_by_index(0)
		product_template = []
		i = 0
		for row_no in range(sheet.nrows):
			i+=1
			if row_no <= 0:
				fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
			else:
				line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
				producto = {}
				producto_line = {
                    "codigo": line[0].strip(),
					"descripcion": line[2].strip(),
				}


				product_product = None
				product_template = self.env["product.template"].search([('default_code','=',producto_line['codigo'])], limit=1)
				if product_template:
					product_product = None
					product_product = self.env["product.product"].search([('product_tmpl_id','=',product_template.id)])
				else:
					product_product = None
					product_template = self.env["product.template"].search([('name','=',producto_line['descripcion'])], limit=1)
					if product_template:
						product_product = self.env["product.product"].search([('product_tmpl_id','=',product_template.id)])

				encontro = False
				cargado = 'nada'
				carga_valor = 0
				if product_product:
					encontro = True


				print("%s |----------%s------------------ %s" % (i,encontro,producto_line))

				with open("/mnt/extra-addons/Comelasa/holaSI.txt", 'a') as f:
					if encontro:
						product_template.origen = 'nacional'
						print("%s|%s|%s|%s|%s|%s" % (
						i,
						producto_line['codigo'],
						producto_line['descripcion'],
						product_product.id,
						product_product.default_code,
						product_product.name,
						), file=f)

				with open("/mnt/extra-addons/Comelasa/holaNO.txt", 'a') as g:
					if not encontro:
						print("%s|%s|%s|%s|%s" % (
							i,
							producto_line['codigo'],
							producto_line['descripcion'],
							False,
							False,
							), file=g)
    
	def _cuandrar_costos(self):
		print("Hola mundoc2")
	
	def _actualizar_productos(self):
		print("Hola a todos")
		keys = ['ID', 'Nombre', 'Imagen']
		csv_data = base64.b64decode(self.archivo)
		data_file = io.StringIO(csv_data.decode("utf-8"))
		data_file.seek(0)
		file_reader = []
		values = {}
		csv_reader = csv.reader(data_file, delimiter=',')
		file_reader.extend(csv_reader)
		contador = 0
		for i in range(len(file_reader)):
			
			contador += 1
			if contador == 1:
				continue
			field = list(map(str, file_reader[i]))
			values = dict(zip(keys, field))
			producto_plantilla = self.env["product.template"].search([('origen_id','=', int(field[0]))])
			for producto in producto_plantilla:
				producto['image_1920'] = field[1]

				print(producto['id'] )

	def _actualizar_pedidos2023(self):
		pedidos = self.env['sale.order'].search([('destino_id','>',0)])
		i=0
		for pedido in pedidos:
			i+=1
			print(pedido.destino_id)
			pedido.state = 'sale'
			pedido.create_date = '2023-12-31'
			factura = self.env['account.move'].browse(pedido.destino_id)
			# pedido.invoice_lines = [(6, 0, factura.invoice_line_ids)] 
   
			if factura:
				print(factura.name)
				total_documento = factura.amount_total

				for linea in pedido.order_line:
					linea.price_unit = total_documento

	def _actualizar_referencia2023(self):
		fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
		fp.write(binascii.a2b_base64(self.archivo))
		fp.seek(0)
		values = []
		workbook = xlrd.open_workbook(fp.name)
		sheet = workbook.sheet_by_index(0)
		product_template = []
		i = 1
		for row_no in range(sheet.nrows):
			if row_no <= 0:
				fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
			else:
				i+=1
				line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
				producto = {}
				producto_line = {
                    "id": line[0],
                    "nombre": line[1].strip(),
					"pedido": int(line[2].strip().replace('.0','')),
					}
				print(i)
				print(producto_line)
				pedido = self.env['sale.order'].search([('destino_id','=',producto_line['pedido'])])
				if pedido:
					pedido.client_order_ref = producto_line['nombre']
