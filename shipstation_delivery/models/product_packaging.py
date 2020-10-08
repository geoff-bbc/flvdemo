# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    package_carrier_type = fields.Selection(selection_add=[('shipstation_ts', 'ShipStation')])
    shipstation_account_id = fields.Many2one('shipstation.accounts','ShipStation Account')
    shipstation_carrier_id = fields.Many2one('shipstation.carrier','ShipStation Carrier')

