from odoo import models, fields, api
from datetime import timedelta


class SpaDriverRouteWizard(models.TransientModel):
    _name = 'spa.driver.route.wizard'
    _description = 'Driver Route Planner'

    car_id = fields.Many2one('spa.car', string='Car', required=True)
    route_date = fields.Date('Date', required=True, default=fields.Date.today)
    driver_id = fields.Many2one('res.users', related='car_id.driver_id', readonly=True)

    appointment_a_id = fields.Many2one(
        'spa.appointment', string='Team A Appointment', compute='_compute_appointments'
    )
    appointment_b_id = fields.Many2one(
        'spa.appointment', string='Team B Appointment', compute='_compute_appointments'
    )
    address_a = fields.Char(related='appointment_a_id.address', readonly=True, string='Address A')
    address_b = fields.Char(related='appointment_b_id.address', readonly=True, string='Address B')
    map_link_a = fields.Char(
        related='appointment_a_id.google_map_link', readonly=True, string='Map Link A'
    )
    map_link_b = fields.Char(
        related='appointment_b_id.google_map_link', readonly=True, string='Map Link B'
    )
    time_a = fields.Datetime(related='appointment_a_id.service_date', readonly=True, string='Time A')
    time_b = fields.Datetime(related='appointment_b_id.service_date', readonly=True, string='Time B')

    route_suggestion = fields.Text('Route Suggestion', compute='_compute_route_suggestion')

    @api.depends('car_id', 'route_date')
    def _compute_appointments(self):
        for wiz in self:
            if not wiz.car_id or not wiz.route_date:
                wiz.appointment_a_id = False
                wiz.appointment_b_id = False
                continue
            date_start = fields.Datetime.to_datetime(wiz.route_date)
            date_end = date_start + timedelta(days=1)
            appts = self.env['spa.appointment'].search([
                ('car_id', '=', wiz.car_id.id),
                ('service_date', '>=', date_start),
                ('service_date', '<', date_end),
                ('status', 'not in', ['cancelled']),
            ])
            wiz.appointment_a_id = appts.filtered(lambda a: a.team_slot == 'a')[:1]
            wiz.appointment_b_id = appts.filtered(lambda a: a.team_slot == 'b')[:1]

    @api.depends('appointment_a_id', 'appointment_b_id')
    def _compute_route_suggestion(self):
        for wiz in self:
            appt_a = wiz.appointment_a_id
            appt_b = wiz.appointment_b_id

            if not appt_a and not appt_b:
                wiz.route_suggestion = 'No appointments found for this car on this date.'
                continue

            if appt_a and not appt_b:
                wiz.route_suggestion = (
                    'STOP 1 — Drop Team A\n'
                    f'  Address : {appt_a.address or "—"}\n'
                    f'  Time    : {appt_a.service_date.strftime("%H:%M") if appt_a.service_date else "—"}\n'
                    f'  Map     : {appt_a.google_map_link or "—"}\n\n'
                    'Only one appointment today.'
                )
                continue

            if appt_b and not appt_a:
                wiz.route_suggestion = (
                    'STOP 1 — Drop Team B\n'
                    f'  Address : {appt_b.address or "—"}\n'
                    f'  Time    : {appt_b.service_date.strftime("%H:%M") if appt_b.service_date else "—"}\n'
                    f'  Map     : {appt_b.google_map_link or "—"}\n\n'
                    'Only one appointment today.'
                )
                continue

            # Both appointments — suggest order by scheduled time
            if appt_a.service_date <= appt_b.service_date:
                first, second = appt_a, appt_b
                first_label, second_label = 'Team A', 'Team B'
            else:
                first, second = appt_b, appt_a
                first_label, second_label = 'Team B', 'Team A'

            wiz.route_suggestion = (
                f'STOP 1 — Drop {first_label}\n'
                f'  Address : {first.address or "—"}\n'
                f'  Time    : {first.service_date.strftime("%H:%M") if first.service_date else "—"}\n'
                f'  Map     : {first.google_map_link or "—"}\n\n'
                f'STOP 2 — Drop {second_label}\n'
                f'  Address : {second.address or "—"}\n'
                f'  Time    : {second.service_date.strftime("%H:%M") if second.service_date else "—"}\n'
                f'  Map     : {second.google_map_link or "—"}\n\n'
                'Driver returns after both teams are deployed.'
            )
