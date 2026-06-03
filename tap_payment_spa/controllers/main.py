import json
import logging

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class TapPaymentController(http.Controller):

    # ── Customer redirect (after payment on Tap hosted page) ─────────────────

    @http.route('/tap/payment/return', type='http', auth='public', csrf=False, save_session=False)
    def tap_payment_return(self, **kwargs):
        """
        Tap redirects the customer here after they complete (or cancel) payment.
        Query params typically include: tap_id, status, etc.
        """
        tap_id = kwargs.get('tap_id') or kwargs.get('charge_id', '')
        status = kwargs.get('status', '').upper()

        _logger.info('Tap return redirect: tap_id=%s status=%s', tap_id, status)

        if tap_id:
            try:
                request.env['spa.appointment'].sudo()._tap_update_payment_status(
                    tap_id, status or 'INITIATED'
                )
            except Exception:
                _logger.exception('Error updating appointment from Tap redirect')

        # Redirect to a simple thank-you page
        if status == 'CAPTURED':
            msg = _('Payment completed successfully. Thank you!')
            css_class = 'alert-success'
        elif status in ('DECLINED', 'FAILED', 'CANCELLED', 'VOID'):
            msg = _('Payment was not completed. Please contact us if you need assistance.')
            css_class = 'alert-danger'
        else:
            msg = _('Your payment is being processed. We will confirm shortly.')
            css_class = 'alert-info'

        return request.render('tap_payment_spa.tap_payment_return_page', {
            'message': msg,
            'css_class': css_class,
            'tap_id': tap_id,
            'status': status,
        })

    # ── Webhook (server-to-server POST from Tap) ──────────────────────────────

    @http.route('/tap/payment/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def tap_payment_webhook(self, **kwargs):
        """
        Tap POSTs the charge result here after payment.
        Body is JSON; Tap also sends a 'hashstring' header for verification.
        """
        try:
            raw_body = request.httprequest.get_data(as_text=True)
            _logger.info('Tap webhook received: %s', raw_body[:500])

            data = json.loads(raw_body) if raw_body else {}
            charge_id = data.get('id', '')
            status = data.get('status', '').upper()

            if charge_id and status:
                request.env['spa.appointment'].sudo()._tap_update_payment_status(
                    charge_id, status
                )
        except Exception:
            _logger.exception('Error processing Tap webhook')
            return request.make_response('ERROR', status=500)

        return request.make_response('OK', status=200)
