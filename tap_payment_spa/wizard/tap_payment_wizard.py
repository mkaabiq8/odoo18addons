import json
import logging
import re
import urllib.request
import urllib.error

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TAP_CHARGES_URL = 'https://api.tap.company/v2/charges/'


def _parse_phone(phone):
    """Return (country_code, local_number) from a phone string.

    Handles common formats:
      +966512345678  → ('966', '512345678')
      00966512345678 → ('966', '512345678')
      0512345678     → ('966', '0512345678')   ← fallback country_code=966 (SA)
      512345678      → ('966', '512345678')
    """
    if not phone:
        return '966', ''
    digits = re.sub(r'\D', '', phone)
    if phone.startswith('+'):
        # e.g. +966512345678 → digits = 966512345678
        country_code = digits[:3] if len(digits) >= 11 else digits[:2]
        local = digits[len(country_code):]
    elif digits.startswith('00'):
        country_code = digits[2:5]
        local = digits[5:]
    elif digits.startswith('0') and len(digits) == 10:
        country_code = '966'
        local = digits
    else:
        # Guess Saudi Arabia if no prefix
        country_code = '966'
        local = digits
    return country_code, local


class TapPaymentWizard(models.TransientModel):
    _name = 'tap.payment.wizard'
    _description = 'Generate Tap Payment Link'

    # ── Source appointment ────────────────────────────────────────────────────

    appointment_id = fields.Many2one(
        'spa.appointment',
        string='Appointment',
        required=True,
        readonly=True,
    )

    # ── Pre-filled payment details (editable before sending) ─────────────────

    amount = fields.Float(
        string='Amount',
        required=True,
        digits=(16, 3),
    )
    currency_code = fields.Char(
        string='Currency',
        required=True,
        default='SAR',
    )
    customer_name = fields.Char(string='Customer Name', readonly=True)
    phone = fields.Char(
        string='Phone (with country code)',
        help='e.g. +966512345678',
    )
    email = fields.Char(string='Email (optional)')
    description = fields.Char(string='Payment Description')

    # ── State / result ────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('draft',     'Ready'),
            ('generated', 'Link Generated'),
            ('error',     'Error'),
        ],
        default='draft',
        readonly=True,
    )
    payment_url = fields.Char(string='Payment Link', readonly=True)
    charge_id = fields.Char(string='Tap Charge ID', readonly=True)
    error_message = fields.Text(string='Error', readonly=True)

    # ── Defaults ─────────────────────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        appt_id = self.env.context.get('default_appointment_id')
        if appt_id:
            appt = self.env['spa.appointment'].browse(appt_id)
            res.update({
                'appointment_id': appt.id,
                'amount': appt.total_amount,
                'currency_code': appt.env.company.currency_id.name or 'SAR',
                'customer_name': appt.customer_id.name if appt.customer_id else '',
                'phone': appt.phone or (
                    appt.customer_id.phone or appt.customer_id.mobile
                    if appt.customer_id else ''
                ),
                'email': appt.customer_id.email if appt.customer_id else '',
                'description': appt.name,
            })
        return res

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_tap_secret_key(self):
        key = self.env['ir.config_parameter'].sudo().get_param('tap_payment.secret_key', '')
        if not key:
            raise UserError(_(
                'Tap secret key is not configured.\n'
                'Go to Settings → Technical → Tap Payment to add your API key.'
            ))
        return key

    def _get_redirect_url(self):
        configured = self.env['ir.config_parameter'].sudo().get_param(
            'tap_payment.redirect_url', ''
        )
        if configured:
            return configured
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', 'http://localhost:8069'
        )
        return base.rstrip('/') + '/tap/payment/return'

    def _get_webhook_url(self):
        configured = self.env['ir.config_parameter'].sudo().get_param(
            'tap_payment.webhook_url', ''
        )
        if configured:
            return configured
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', 'http://localhost:8069'
        )
        return base.rstrip('/') + '/tap/payment/webhook'

    def _build_customer_payload(self):
        """Build the customer object expected by Tap Charges API."""
        name_parts = (self.customer_name or '').split(' ', 1)
        first = name_parts[0] or 'Customer'
        last = name_parts[1] if len(name_parts) > 1 else '.'

        country_code, local_number = _parse_phone(self.phone)

        customer = {
            'first_name': first,
            'last_name': last,
        }
        if local_number:
            customer['phone'] = {
                'country_code': country_code,
                'number': local_number,
            }
        if self.email:
            customer['email'] = self.email
        return customer

    # ── Main action: call Tap API ─────────────────────────────────────────────

    def action_generate_link(self):
        """Call Tap Charges API and store the resulting payment link."""
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('Amount must be greater than zero.'))

        secret_key = self._get_tap_secret_key()

        payload = {
            'amount': round(self.amount, 3),
            'currency': (self.currency_code or 'SAR').upper(),
            'customer_initiated': True,
            'threeDSecure': True,
            'save_card': False,
            'description': self.description or self.appointment_id.name,
            'reference': {
                'transaction': self.appointment_id.name,
                'order': self.appointment_id.name,
            },
            'customer': self._build_customer_payload(),
            'merchant': {},
            'source': {'id': 'src_all'},
            'redirect': {'url': self._get_redirect_url()},
            'post': {'url': self._get_webhook_url()},
        }

        # Add merchant ID if configured
        merchant_id = self.env['ir.config_parameter'].sudo().get_param(
            'tap_payment.merchant_id', ''
        )
        if merchant_id:
            payload['merchant'] = {'id': merchant_id}

        _logger.info('Tap Payment: creating charge for appointment %s, amount %s %s',
                     self.appointment_id.name, payload['amount'], payload['currency'])

        try:
            body = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                TAP_CHARGES_URL,
                data=body,
                method='POST',
                headers={
                    'Authorization': 'Bearer ' + secret_key,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                response_data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode('utf-8', errors='replace')
            _logger.error('Tap API HTTP error %s: %s', exc.code, error_body)
            self.write({
                'state': 'error',
                'error_message': 'HTTP %s: %s' % (exc.code, error_body[:500]),
            })
            return self._reopen()
        except Exception as exc:
            _logger.exception('Tap API unexpected error')
            self.write({
                'state': 'error',
                'error_message': str(exc)[:500],
            })
            return self._reopen()

        # ── Parse response ────────────────────────────────────────────────────

        charge_id = response_data.get('id', '')
        tap_status = response_data.get('status', 'INITIATED')
        transaction = response_data.get('transaction', {})
        pay_url = transaction.get('url', '') or response_data.get('url', '')

        if not pay_url:
            self.write({
                'state': 'error',
                'error_message': _(
                    'Tap returned no payment URL. Response: %s'
                ) % json.dumps(response_data)[:500],
            })
            return self._reopen()

        # ── Persist on appointment ────────────────────────────────────────────

        self.appointment_id.sudo().write({
            'tap_charge_id': charge_id,
            'tap_payment_url': pay_url,
            'tap_payment_status': tap_status,
            'tap_payment_generated_at': fields.Datetime.now(),
        })
        self.appointment_id.message_post(
            body=_('Tap payment link generated: <a href="%s">%s</a>') % (pay_url, pay_url),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        _logger.info('Tap Payment: charge %s created, URL: %s', charge_id, pay_url)

        self.write({
            'state': 'generated',
            'payment_url': pay_url,
            'charge_id': charge_id,
        })
        return self._reopen()

    def _reopen(self):
        """Return an action that re-opens this same wizard record."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Tap Payment Link'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
