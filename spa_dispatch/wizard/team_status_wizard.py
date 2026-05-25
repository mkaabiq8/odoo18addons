from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SpaTeamStatusWizard(models.TransientModel):
    """Quick status update wizard for team members in the field."""
    _name = 'spa.team.status.wizard'
    _description = 'Team Field Status Update'

    appointment_id = fields.Many2one('spa.appointment', string='Appointment', readonly=True)
    customer_name = fields.Char(related='appointment_id.customer_id.name', readonly=True)
    address = fields.Char(related='appointment_id.address', readonly=True)
    current_status = fields.Selection(related='appointment_id.status', readonly=True)
    new_status = fields.Selection([
        ('traveling',   'We are on our way'),
        ('arrived',     'We have arrived'),
        ('in_progress', 'Session in progress'),
        ('done',        'Session completed'),
    ], string='Update Status To', required=True)
    note = fields.Text('Note (optional)')

    def action_apply(self):
        self.ensure_one()
        appt = self.appointment_id
        # Only allow team members of this appointment to update
        if self.env.user not in appt.technician_ids and self.env.user != appt.driver_id:
            if not self.env.user.has_group('spa_dispatch.group_spa_manager'):
                raise UserError(_('You are not assigned to this appointment.'))
        appt.write({'status': self.new_status})
        if self.note:
            appt.message_post(body=f'Field update by {self.env.user.name}: {self.note}')
        return {'type': 'ir.actions.act_window_close'}
