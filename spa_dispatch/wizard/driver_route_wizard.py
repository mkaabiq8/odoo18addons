from odoo import models, fields, api
import math


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
    time_a = fields.Datetime(related='appointment_a_id.service_date', readonly=True, string='Time A')
    time_b = fields.Datetime(related='appointment_b_id.service_date', readonly=True, string='Time B')

    route_suggestion = fields.Text('Route Suggestion', compute='_compute_route_suggestion')
    distance_km = fields.Float('Estimated Distance (km)', compute='_compute_route_suggestion')

    @api.depends('car_id', 'route_date')
    def _compute_appointments(self):
        for wiz in self:
            if not wiz.car_id or not wiz.route_date:
                wiz.appointment_a_id = False
                wiz.appointment_b_id = False
                continue
            appts = self.env['spa.appointment'].search([
                ('car_id', '=', wiz.car_id.id),
                ('service_date', '>=', fields.Datetime.to_datetime(wiz.route_date)),
                ('service_date', '<', fields.Datetime.to_datetime(wiz.route_date) + fields.relativedelta(days=1)
                 if hasattr(fields, 'relativedelta') else
                 fields.Datetime.to_datetime(str(wiz.route_date) + ' 23:59:59')),
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
                wiz.distance_km = 0.0
                continue

            if appt_a and not appt_b:
                wiz.route_suggestion = f'Drop Team A at: {appt_a.address}\nOnly one appointment today.'
                wiz.distance_km = 0.0
                continue

            if appt_b and not appt_a:
                wiz.route_suggestion = f'Drop Team B at: {appt_b.address}\nOnly one appointment today.'
                wiz.distance_km = 0.0
                continue

            # Both appointments exist — suggest order by scheduled time
            if appt_a.service_date <= appt_b.service_date:
                first, second = appt_a, appt_b
                first_label, second_label = 'Team A', 'Team B'
            else:
                first, second = appt_b, appt_a
                first_label, second_label = 'Team B', 'Team A'

            # Calculate distance between the two locations if GPS available
            dist = 0.0
            if (first.latitude and first.longitude and second.latitude and second.longitude):
                dist = wiz._haversine(
                    first.latitude, first.longitude,
                    second.latitude, second.longitude
                )

            wiz.distance_km = dist
            dist_txt = f' (~{dist:.1f} km between stops)' if dist else ''
            wiz.route_suggestion = (
                f'STOP 1 — Drop {first_label}\n'
                f'  Address : {first.address}\n'
                f'  Time    : {first.service_date.strftime("%H:%M") if first.service_date else "—"}\n\n'
                f'STOP 2 — Drop {second_label}{dist_txt}\n'
                f'  Address : {second.address}\n'
                f'  Time    : {second.service_date.strftime("%H:%M") if second.service_date else "—"}\n\n'
                f'Driver returns after both teams are deployed.'
            )

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2
             + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
