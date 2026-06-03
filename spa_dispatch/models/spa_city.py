from odoo import models, fields


class SpaCity(models.Model):
    _name = 'spa.city'
    _description = 'Service City'
    _order = 'state_id, name'

    name = fields.Char('City Name', required=True)
    state_id = fields.Many2one('res.country.state', string='State / Emirate')
    active = fields.Boolean(default=True)
