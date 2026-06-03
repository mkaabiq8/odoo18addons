from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Tap API credentials ───────────────────────────────────────────────────

    tap_secret_key = fields.Char(
        string='Tap Secret Key',
        config_parameter='tap_payment.secret_key',
        help='Backend secret key from Tap Dashboard (sk_live_xxx / sk_test_xxx).'
             ' Never expose this in the frontend.',
    )
    tap_public_key = fields.Char(
        string='Tap Public Key',
        config_parameter='tap_payment.public_key',
        help='Frontend public key from Tap Dashboard (pk_live_xxx / pk_test_xxx).',
    )
    tap_merchant_id = fields.Char(
        string='Tap Merchant ID',
        config_parameter='tap_payment.merchant_id',
        help='Merchant ID shown in Tap Dashboard → Accounts → Operators.',
    )

    # ── Mode ─────────────────────────────────────────────────────────────────

    tap_test_mode = fields.Boolean(
        string='Test Mode',
        config_parameter='tap_payment.test_mode',
        default=True,
        help='When enabled, charges are created in Tap sandbox. '
             'Switch off for live production payments.',
    )

    # ── Redirect / Webhook URLs ───────────────────────────────────────────────

    tap_redirect_url = fields.Char(
        string='Payment Return URL',
        config_parameter='tap_payment.redirect_url',
        help='URL Tap redirects the customer to after payment. '
             'Defaults to <odoo_base_url>/tap/payment/return if left blank.',
    )
    tap_webhook_url = fields.Char(
        string='Webhook URL',
        config_parameter='tap_payment.webhook_url',
        help='URL Tap POSTs the payment result to (server-to-server). '
             'Defaults to <odoo_base_url>/tap/payment/webhook if left blank.',
    )
