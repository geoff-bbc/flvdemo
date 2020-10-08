from odoo import fields, models, api, _
import dateutil.parser
from odoo.exceptions import Warning, ValidationError


class ExportShipstationOrder(models.TransientModel):
    _name = 'export.shipstation.order'
    _description = 'Export Shipstation order'

    def convert_product_weight(self, weight):
        weight_uom_id = self.env.ref('uom.product_uom_oz', raise_if_not_found=False)
        to_weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        return weight_uom_id._compute_quantity(weight, to_weight_uom_id, round=False)

    '''For Export Shipstation order through api '''

    def prepare_export_data(self):
        stock_picking_obj = self.env['stock.picking']
        pickings = stock_picking_obj.browse(self._context.get('active_ids'))
        stock_picking_ids = self.env['stock.picking'].search([('is_exported_to_shipstation', '=', False),
                                                              ('sale_id', '!=', False),
                                                              ('sale_id.shipstation_store_id', '!=', False),
                                                              ('sale_id.shipstation_account_id', '!=', False),
                                                              ('state', 'not in', ['cancel', 'draft', 'done']),
                                                              ('picking_type_id.code', '=', 'outgoing'),
                                                              ])   
        for picking in pickings or stock_picking_ids:
            order = picking.sale_id
            shipstation_store_id = order.shipstation_store_id
            carrier_id = picking.carrier_id or order.carrier_id
            if not shipstation_store_id or not order.shipstation_account_id:
                continue
            if picking.state == 'cancel':
                raise Warning('You can not export cancel order..!')
            if not carrier_id:
                raise Warning('Delivery method not found in order..!')
            if not carrier_id.delivery_type == "shipstation_ts":
                raise Warning('Delivery method must have shipstation provider..!')
            if not carrier_id.shipstation_package_id:
                raise Warning('Shipstation Package not found in carrier..!')
            if not carrier_id.shipstation_service_id:
                raise Warning('Service is not being set in carrier..!')

            shipstation_store_id = order.shipstation_store_id
            account = shipstation_store_id.account_id
            package = carrier_id.shipstation_package_id
            date_order_format = (order.date_order.strftime("%Y-%m-%dT%H:%M:%S.0000000"))
            scheduled_date_format = (order.date_order.strftime("%Y-%m-%dT%H:%M:%S.0000000"))

            est_weight_value = sum([(line.product_id.weight * line.product_uom_qty) for line in
                                    order.order_line.filtered(
                                        lambda x: not x.product_id.type in ['service', 'digital'])]) or 0.0

            shipstation_warehouse = self.env['shipstation.warehouse'].search([('warehouse_id', '=', order.warehouse_id.id), ('account_id', '=', order.shipstation_account_id.id)], limit=1)
            if not shipstation_warehouse:
                raise Warning('Shipstation Warehouse not found..!')
            order_key = order.shipstation_order_key or order.name

            partner_shipping_id = order.partner_shipping_id
            partner_invoice_id = order.partner_invoice_id
            est_weight_value = est_weight_value * 35.274
            weight = self.convert_product_weight(est_weight_value)
            data = {
                "orderNumber": order.name,
                "orderKey": order_key,
                "orderDate": date_order_format,
                "shipByDate": scheduled_date_format,
                "orderStatus": "awaiting_shipment",
                "customerUsername": partner_shipping_id.name,
                "customerEmail": partner_shipping_id.email,
                "carrierCode": carrier_id.shipstation_carrier_id.code,
                # "shippingAmount": shipping_rates,
                "serviceCode": carrier_id.shipstation_service_id.code,
                "packageCode": package.code,
                "weight": {
                    "value": weight,
                    "units": 'ounces'
                },
                "billTo": {
                    "name": partner_invoice_id.name or '',
                    "company": partner_invoice_id.name if partner_invoice_id.is_company else '',
                    "street1": partner_invoice_id.street or '',
                    "street2": partner_invoice_id.street2 or '',
                    "city": partner_invoice_id.city or '',
                    "state": partner_invoice_id.state_id.code or '',
                    "postalCode": partner_invoice_id.zip or '',
                    "country": partner_invoice_id.country_id.code or '',
                    "phone": partner_invoice_id.phone or '',
                },

                "shipTo": {
                    "name": partner_shipping_id.name or '',
                    "company": partner_shipping_id.name if partner_shipping_id.is_company else '',
                    "street1": partner_shipping_id.street or '',
                    "street2": partner_shipping_id.street2 or '',
                    "city": partner_shipping_id.city or '',
                    "state": partner_shipping_id.state_id.code or '',
                    "postalCode": partner_shipping_id.zip or '',
                    "country": partner_shipping_id.country_id.code or '',
                    "phone": partner_shipping_id.phone or '',
                },

                "advancedOptions": {
                    "warehouseId": shipstation_warehouse.shipstation_id,
                    "storeId": shipstation_store_id.store_id}
            }

            if package.is_your_packaging:
                data.update({"packageCode": 'package',
                             "dimensions":
                                 {
                                     "units": "inches",
                                     "height": package.packaging_id.height,
                                     "length": package.packaging_id.length,
                                     "width": package.packaging_id.width
                                 }})

            line_list = []
            for pmove in picking.move_ids_without_package:
                ship_product_id = self.env['shipstation.product'].search([('product_id', '=', pmove.product_id.id), ('account_id', '=', order.shipstation_account_id.id)])
                product_weight = pmove.product_id.weight * 35.274
                line_weight = self.convert_product_weight(product_weight)
                price = float(pmove.product_id.lst_price)
                product_dict = {
                    "lineItemKey": pmove.product_id.id,
                    "sku": pmove.product_id.default_code or '',
                    "name": pmove.product_id.name or '',
                    "weight": {
                        "value": line_weight
                    },
                    "quantity": int(pmove.product_qty),
                    "unitPrice": price,
                    "taxAmount": 0.0,
                    "options": [
                        {
                            "name": "",
                            "value": ""
                        }
                    ],
                }
                line_list.append(product_dict)
            data.update({'items': line_list})

            try:
                response = account._send_request('/orders/createorder', data,
                                                 method="POST")
            except Exception as e:
                raise ValidationError(e)
            if not response:
                raise ValidationError("Didn't get replay from Shipstaion")
            order.write({'shipstation_order_id': response.get('orderId'),
                         'shipstation_order_key': response.get('orderKey'),
                         'shipstation_store_id':shipstation_store_id.id,
                         'shipstation_account_id':account.id,
                         'is_exported_to_shipstation': True})
            picking.write({'is_exported_to_shipstation': True, 'shipstation_store_id':shipstation_store_id.id, 'shipstation_order_id': response.get('orderId')})

            return True
