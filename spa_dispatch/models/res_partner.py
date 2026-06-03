from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    spa_city_id = fields.Many2one(
        'spa.city', string='Service City',
        help='Preferred service city remembered from last spa home visit booking.'
    )
