from odoo import models, fields


class SpaZone(models.Model):
    _name = 'spa.zone'
    _description = 'Service Zone / Area'
    _order = 'name'

    name = fields.Char('Zone Name', required=True, translate=True)
    active = fields.Boolean(default=True)
    notes = fields.Text('Notes')
