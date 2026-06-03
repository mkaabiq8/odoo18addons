from odoo import models, fields, api


class SpaTeam(models.Model):
    _name = 'spa.team'
    _description = 'Spa Service Team'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    name = fields.Char('Team Name', required=True, tracking=True)
    zone_id = fields.Many2one('spa.zone', string='Zone / Area', tracking=True)
    car_id = fields.Many2one(
        'spa.car', string='Zone', required=True, tracking=True, ondelete='cascade'
    )
    slot = fields.Selection(
        [('a', 'Team A'), ('b', 'Team B')],
        string='Slot', required=True, tracking=True
    )
    member_ids = fields.Many2many(
        'res.users', 'spa_team_user_rel', 'team_id', 'user_id',
        string='Team Members'
    )
    active = fields.Boolean(default=True)
    notes = fields.Text('Notes')

    display_name = fields.Char(compute='_compute_display_name', store=True)
    appointment_count = fields.Integer(compute='_compute_appointment_count')

    @api.depends('name', 'car_id', 'slot')
    def _compute_display_name(self):
        for team in self:
            slot_label = 'Team A' if team.slot == 'a' else 'Team B'
            car_name = team.car_id.name if team.car_id else ''
            team.display_name = f'{car_name} – {slot_label} ({team.name})'

    def _compute_appointment_count(self):
        for team in self:
            team.appointment_count = self.env['spa.appointment'].search_count([
                ('team_id', '=', team.id),
                ('status', 'not in', ['cancelled']),
            ])

    def action_view_appointments(self):
        self.ensure_one()
        return {
            'name': f'{self.display_name} – Appointments',
            'type': 'ir.actions.act_window',
            'res_model': 'spa.appointment',
            'view_mode': 'list,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id, 'default_car_id': self.car_id.id},
        }

    _sql_constraints = [
        ('unique_car_slot', 'unique(car_id, slot)',
         'Each car can only have one Team A and one Team B.')
    ]
