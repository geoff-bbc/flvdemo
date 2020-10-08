from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    shipstation_shipment_id = fields.Char("ShipStation Shipment ID")
    is_exported_to_shipstation = fields.Boolean("Exported to shipstation?", copy=False)
    shipstation_store_id = fields.Many2one('shipstation.store', "Store", ondelete='restrict', copy=False)
    shipstation_order_id = fields.Char('Order ID', help="The system generated identifier for the order.", readonly=True, copy=False)
