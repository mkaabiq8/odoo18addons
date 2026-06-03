from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class SpaAppointment(models.Model):
    _name = 'spa.appointment'
    _description = 'Spa Home Service Appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'service_date asc, name asc'
    _rec_name = 'name'

    # ─── Reference ───────────────────────────────────────────────────────────
    name = fields.Char(
        'Reference', readonly=True, copy=False, default='New', tracking=True
    )

    # ─── Customer ────────────────────────────────────────────────────────────
    customer_id = fields.Many2one(
        'res.partner', string='Customer', required=True, tracking=True
    )
    phone = fields.Char('Phone', compute='_compute_phone', store=True, readonly=False)
    address = fields.Char('Service Address', required=True, tracking=True)

    # ─── Location ────────────────────────────────────────────────────────────
    state_id = fields.Many2one(
        'res.country.state', string='State / Area', tracking=True
    )
    city_id = fields.Many2one(
        'spa.city', string='City',
        domain="[('state_id', '=', state_id)]",
        tracking=True
    )
    google_map_link = fields.Char('Google Maps Link')

    # ─── Schedule ────────────────────────────────────────────────────────────
    service_date = fields.Datetime(
        'Appointment Date/Time', required=True, tracking=True
    )
    duration = fields.Float('Duration (hrs)', default=1.5, tracking=True)
    service_end_date = fields.Datetime(
        'End Time', compute='_compute_end_date', store=True
    )

    # ─── Services ────────────────────────────────────────────────────────────
    service_line_ids = fields.One2many(
        'spa.appointment.line', 'appointment_id', string='Services'
    )
    total_amount = fields.Float(
        'Total', compute='_compute_total', store=True
    )

    # ─── Dispatch ────────────────────────────────────────────────────────────
    car_id = fields.Many2one('spa.car', string='Zone', tracking=True)
    team_slot = fields.Selection(
        [('a', 'Team A'), ('b', 'Team B')],
        string='Team Slot', tracking=True
    )
    team_id = fields.Many2one(
        'spa.team', string='Team', tracking=True,
        domain="[('car_id', '=', car_id), ('slot', '=', team_slot)]"
    )
    driver_id = fields.Many2one(
        'res.users', string='Driver', related='car_id.driver_id', store=True
    )
    technician_ids = fields.Many2many(
        'res.users', string='Technicians',
        compute='_compute_technicians', store=True
    )

    # ─── Status ──────────────────────────────────────────────────────────────
    status = fields.Selection([
        ('draft',       'Pending'),
        ('confirmed',   'Confirmed'),
        ('traveling',   'Team Traveling'),
        ('arrived',     'Team Arrived'),
        ('in_progress', 'In Progress'),
        ('done',        'Completed'),
        ('cancelled',   'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True, index=True)

    # ─── Meta ─────────────────────────────────────────────────────────────────
    agent_id = fields.Many2one(
        'res.users', string='Booked By',
        default=lambda self: self.env.user, tracking=True
    )
    crm_lead_id = fields.Many2one('crm.lead', string='CRM Lead / Call')
    notes = fields.Text('Internal Notes')
    customer_notes = fields.Text('Customer Notes')

    # ─── Kanban color ────────────────────────────────────────────────────────
    color = fields.Integer(compute='_compute_color')
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], default='0'
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Sequence + create/write overrides
    # ─────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('spa.appointment') or 'New'
                )
        records = super().create(vals_list)
        records._sync_to_partner()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'state_id', 'city_id', 'address', 'phone'} & set(vals.keys()):
            self._sync_to_partner()
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Computed fields
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('customer_id')
    def _compute_phone(self):
        for rec in self:
            if rec.customer_id and not rec.phone:
                rec.phone = rec.customer_id.phone or rec.customer_id.mobile

    def _compute_display_name(self):
        """Rich display name shown on calendar cards and breadcrumbs."""
        status_labels = {
            'draft':       'Pending',
            'confirmed':   'Confirmed',
            'traveling':   'Traveling',
            'arrived':     'Arrived',
            'in_progress': 'In Progress',
            'done':        'Done',
            'cancelled':   'Cancelled',
        }
        slot_labels = {'a': 'Team A', 'b': 'Team B'}
        for rec in self:
            # Line 1: reference + status — always visible even on small cards
            status_str = status_labels.get(rec.status, '')
            ref = rec.name or 'New'
            lines = [f'{ref}  [{status_str}]' if status_str else ref]
            # Line 2: customer name
            if rec.customer_id:
                lines.append(rec.customer_id.name)
            # Line 3: zone · city · team slot
            details = ' · '.join(filter(None, [
                rec.car_id.name if rec.car_id else '',
                rec.city_id.name if rec.city_id else '',
                slot_labels.get(rec.team_slot, '') if rec.team_slot else '',
            ]))
            if details:
                lines.append(details)
            rec.display_name = '\n'.join(lines)

    @api.depends('service_date', 'duration')
    def _compute_end_date(self):
        for rec in self:
            if rec.service_date and rec.duration:
                rec.service_end_date = rec.service_date + timedelta(hours=rec.duration)
            else:
                rec.service_end_date = rec.service_date

    @api.depends('service_line_ids.subtotal')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.service_line_ids.mapped('subtotal'))

    @api.depends('team_id', 'team_id.member_ids')
    def _compute_technicians(self):
        for rec in self:
            rec.technician_ids = rec.team_id.member_ids if rec.team_id else False

    @api.depends('status')
    def _compute_color(self):
        color_map = {
            'draft':       0,
            'confirmed':   3,
            'traveling':   4,
            'arrived':     2,
            'in_progress': 6,
            'done':        10,
            'cancelled':   1,
        }
        for rec in self:
            rec.color = color_map.get(rec.status, 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Onchanges
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('car_id', 'team_slot')
    def _onchange_car_slot(self):
        """Auto-fill team when car and slot are set."""
        self.team_id = False
        if self.car_id and self.team_slot:
            team = self.env['spa.team'].search([
                ('car_id', '=', self.car_id.id),
                ('slot', '=', self.team_slot),
            ], limit=1)
            self.team_id = team

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        """Auto-fill phone, address, state and city from the customer record."""
        if self.customer_id:
            partner = self.customer_id
            self.phone = partner.phone or partner.mobile
            if partner.state_id:
                self.state_id = partner.state_id
            if partner.spa_city_id:
                self.city_id = partner.spa_city_id
            if partner.street:
                parts = [partner.street, partner.street2, partner.city]
                self.address = ', '.join(p for p in parts if p)

    @api.onchange('state_id')
    def _onchange_state_id(self):
        """Clear city when state changes to prevent a state/city mismatch."""
        if self.city_id and self.city_id.state_id != self.state_id:
            self.city_id = False

    # ─────────────────────────────────────────────────────────────────────────
    # Partner sync
    # ─────────────────────────────────────────────────────────────────────────

    def _sync_to_partner(self):
        """Write location fields back to the customer so they auto-fill next time."""
        for rec in self:
            if not rec.customer_id:
                continue
            partner = rec.customer_id
            vals = {}
            if rec.state_id and rec.state_id != partner.state_id:
                vals['state_id'] = rec.state_id.id
            if rec.city_id and rec.city_id != partner.spa_city_id:
                vals['spa_city_id'] = rec.city_id.id
            if rec.address and not partner.street:
                vals['street'] = rec.address
            if rec.phone and not partner.phone and not partner.mobile:
                vals['phone'] = rec.phone
            if vals:
                partner.sudo().write(vals)

    # ─────────────────────────────────────────────────────────────────────────
    # Status transitions
    # ─────────────────────────────────────────────────────────────────────────

    def action_confirm(self):
        for rec in self:
            rec._check_dispatch_required()
        self.write({'status': 'confirmed'})

    def action_traveling(self):
        self.write({'status': 'traveling'})

    def action_arrived(self):
        self.write({'status': 'arrived'})

    def action_start(self):
        self.write({'status': 'in_progress'})

    def action_done(self):
        self.write({'status': 'done'})

    def action_cancel(self):
        self.write({'status': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'status': 'draft'})

    def _check_dispatch_required(self):
        """Ensure car and team are set before confirming."""
        for rec in self:
            if not rec.car_id or not rec.team_slot or not rec.team_id:
                raise ValidationError(
                    _('Please assign a Car and Team before confirming appointment %s.') % rec.name
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Payment link
    # ─────────────────────────────────────────────────────────────────────────

    def action_generate_payment_link(self):
        """Open the Odoo payment link wizard pre-filled with appointment data."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Payment Link'),
            'res_model': 'payment.link.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'spa.appointment',
                'default_res_id': self.id,
                'default_amount': self.total_amount,
                'default_currency_id': self.env.company.currency_id.id,
                'default_partner_id': self.customer_id.id if self.customer_id else False,
                'default_description': self.name,
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('service_date', 'duration', 'car_id', 'team_slot', 'status')
    def _check_no_overlap(self):
        for rec in self:
            if not rec.car_id or not rec.team_slot or not rec.service_date:
                continue
            if rec.status == 'cancelled':
                continue
            rec_end = rec.service_date + timedelta(hours=rec.duration or 1.5)
            overlaps = self.search([
                ('id', '!=', rec.id),
                ('car_id', '=', rec.car_id.id),
                ('team_slot', '=', rec.team_slot),
                ('status', 'not in', ['cancelled']),
                ('service_date', '<', rec_end),
                ('service_end_date', '>', rec.service_date),
            ])
            if overlaps:
                raise ValidationError(_(
                    'Scheduling conflict: %(car)s / %(slot)s already has appointment '
                    '"%(other)s" during this time. Please choose a different slot or time.'
                ) % {
                    'car': rec.car_id.name,
                    'slot': 'Team A' if rec.team_slot == 'a' else 'Team B',
                    'other': overlaps[0].name,
                })

    @api.constrains('phone', 'status')
    def _check_unique_active_phone(self):
        """Block duplicate phone numbers across all non-closed appointments."""
        for rec in self:
            if not rec.phone or rec.status in ('done', 'cancelled'):
                continue
            duplicate = self.search([
                ('id', '!=', rec.id),
                ('phone', '=', rec.phone),
                ('status', 'not in', ['done', 'cancelled']),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Phone %(phone)s is already linked to active appointment %(ref)s. '
                    'Complete or cancel that appointment first, or use a different number.'
                ) % {
                    'phone': rec.phone,
                    'ref': duplicate.name,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # Driver route
    # ─────────────────────────────────────────────────────────────────────────

    def action_driver_route(self):
        """Open the driver route wizard for this car's day appointments."""
        self.ensure_one()
        return {
            'name': _('Driver Route – %s') % self.car_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'spa.driver.route.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_car_id': self.car_id.id,
                'default_route_date': (
                    self.service_date.date() if self.service_date else fields.Date.today()
                ),
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Appointment Service Lines
# ─────────────────────────────────────────────────────────────────────────────

class SpaAppointmentLine(models.Model):
    _name = 'spa.appointment.line'
    _description = 'Appointment Service Line'

    appointment_id = fields.Many2one(
        'spa.appointment', required=True, ondelete='cascade'
    )
    service_id = fields.Many2one(
        'product.product', string='Service', required=True,
        domain=[('sale_ok', '=', True)]
    )
    description = fields.Char(
        'Description', compute='_compute_description', store=True, readonly=False
    )
    quantity = fields.Float('Qty', default=1.0)
    price_unit = fields.Float('Unit Price')
    subtotal = fields.Float(compute='_compute_subtotal', store=True)

    @api.depends('service_id')
    def _compute_description(self):
        for line in self:
            line.description = line.service_id.description_sale or line.service_id.name

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            self.price_unit = self.service_id.lst_price

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
