{
    "name": "Enmasys Project Purchase",
    "author": "Huu Cozg",
    "license": "LGPL-3",
    "version": "19.0.1.0",
    "depends": ["base", "purchase", "mail", "hr", "stock"],
    "data": [
        "security/purchase_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/purchase_request_views.xml",
        "views/purchase_order_inherit_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "application": True,
}