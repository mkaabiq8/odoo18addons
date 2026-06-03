{
    'name': 'Spa Home Service Dispatch',
    'version': '18.0.1.0.0',
    'category': 'Services',
    'summary': 'Appointment scheduling and team dispatch for mobile home spa services',
    'description': """
        Manage home spa service appointments with vehicle and team dispatch.
        - 4 cars, each with Team A and Team B
        - Agent books appointments, assigns car + team slot
        - Driver view shows route order for the day
        - Team members update appointment status from the field
        - Conflict detection prevents double-booking
    """,
    'author': 'Jolity',
    'depends': ['base', 'mail', 'sale_management', 'payment'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/spa_zone_views.xml',
        'views/spa_city_views.xml',
        'views/spa_car_views.xml',
        'views/spa_team_views.xml',
        'views/appointment_views.xml',
        'views/dispatch_board_views.xml',
        'views/driver_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'icon': '/spa_dispatch/static/description/icon.png',
}
