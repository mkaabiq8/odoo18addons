from odoo import models, fields, api


class SpaCar(models.Model):
    _name = 'spa.car'
    _description = 'Spa Service Vehicle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Vehicle Name', required=True, tracking=True)
    fleet_vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Fleet Vehicle',
        help='Link to the Fleet module vehicle record'
    )
    driver_id = fields.Many2one(
        'res.users', string='Driver', required=True, tracking=True
    )
    color = fields.Integer('Color Index', default=0)
    active = fields.Boolean(default=True)
    notes = fields.Text('Notes')

    team_ids = fields.One2many('spa.team', 'car_id', string='Teams')
    team_a_id = fields.Many2one(
        'spa.team', string='Team A', compute='_compute_teams', store=True
    )
    team_b_id = fields.Many2one(
        'spa.team', string='Team B', compute='_compute_teams', store=True
    )

    appointment_count = fields.Integer(
        compute='_compute_appointment_count', string='Appointments'
    )
    today_appointment_count = fields.Integer(
        compute='_compute_appointment_count', string="Today's Appointments"
    )

    @api.depends('team_ids', 'team_ids.slot')
    def _compute_teams(self):
        for car in self:
            car.team_a_id = car.team_ids.filtered(lambda t: t.slot == 'a')[:1]
            car.team_b_id = car.team_ids.filtered(lambda t: t.slot == 'b')[:1]

    def _compute_appointment_count(self):
        today = fields.Date.today()
        for car in self:
            all_appts = self.env['spa.appointment'].search([
                ('car_id', '=', car.id),
                ('status', 'not in', ['cancelled']),
            ])
            car.appointment_count = len(all_appts)
            car.today_appointment_count = len(all_appts.filtered(
                lambda a: a.service_date and a.service_date.date() == today
            ))

    def action_view_appointments(self):
        self.ensure_one()
        return {
            'name': f'{self.name} – Appointments',
            'type': 'ir.actions.act_window',
            'res_model': 'spa.appointment',
            'view_mode': 'list,form,calendar',
            'domain': [('car_id', '=', self.id)],
            'context': {'default_car_id': self.id},
        }
