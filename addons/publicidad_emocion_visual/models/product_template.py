from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    centro_comercial = fields.Selection(
        selection=[
            ("viva", "Viva"),
            ("buenavista", "Buenavista"),
            ("mallplaza", "Mallplaza"),
            ("unico", "Unico"),
            ("plaza_central", "Plaza Central"),
        ],
        string="Centro Comercial",
    )
    ubicacion_macro = fields.Selection(
        selection=[
            ("fachada", "Fachada"),
            ("entrada", "Entrada"),
            ("pasillo", "Pasillo"),
            ("plazoleta", "Plazoleta de Comidas"),
        ],
        string="Ubicación Macro",
    )
    basic_ubicacion_detalle = fields.Char(
        string="Ubicación Detalle",
        help="Ej: Piso 1, frente a Juan Valdez",
    )
    formato_id = fields.Selection(
        selection=[
            ("pantalla_led", "Pantalla LED"),
            ("valla", "Valla"),
            ("caja_luz", "Caja de Luz"),
            ("totem", "Totem Digital"),
        ],
        string="Formato",
    )
    tipo_contenido = fields.Selection(
        selection=[
            ("estatico", "Estático"),
            ("video", "Video"),
            ("hibrido", "Híbrido"),
        ],
        string="Tipo de Contenido",
    )
    x_estado_tecnico = fields.Selection(
        selection=[
            ("operativo", "Operativo"),
            ("mantenimiento", "En Mantenimiento"),
            ("averiado", "Fuera de Servicio"),
        ],
        string="Estado Técnico",
        default="operativo",
        help="Estado técnico del activo físico.",
    )
    tamano = fields.Char(string="Tamaño / Dimensiones")
