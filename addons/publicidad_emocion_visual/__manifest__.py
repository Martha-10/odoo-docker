{
    "name": "Publicidad Suscripciones",
    "summary": "Gestión de suscripciones de pautas publicitarias con pago de contado.",
    "version": "18.0.1.0.0",
    "author": "Antigravity",
    "website": "https://example.com",
    "license": "LGPL-3",
    "category": "Sales",
    "depends": [
        "base",
        "product",
        "account",
        "sale",
        "mail",
    ],
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "views/publicidad_suscripcion_views.xml",
        "views/contrato_marco_views.xml",
        "data/publicidad_tax_data.xml",
    ],
    "application": True,
}