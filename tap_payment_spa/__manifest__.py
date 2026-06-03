{
    'name': 'Tap Payment – Spa Dispatch',
    'version': '18.0.1.0.0',
    'category': 'Payment',
    'summary': 'Generate Tap Payment hosted-page links directly from Spa appointments',
    'description': """
        Integrates Tap Payments (https://tap.company) with the Spa Dispatch module.

        Features:
        - Configure Tap secret/public keys and merchant ID in Settings
        - "Generate Tap Payment Link" button on every appointment
        - Calls Tap Charges API (src_all) → returns hosted payment-page URL
        - Stores Tap charge ID, payment URL, and payment status on the appointment
        - Webhook controller updates appointment status when Tap confirms payment
        - Supports test mode / live mode toggle
    """,
    'author': 'Jolity',
    'depends': ['spa_dispatch'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/tap_payment_wizard_views.xml',
        'views/appointment_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
