from odoo import fields, models


class ContratoMarco(models.Model):
    _name = "contrato.marco"
    _description = "Contrato Marco"
    _order = "name desc"

    name = fields.Char(
        string="Número de Contrato",
        required=True,
        copy=False,
        help="Referencia del contrato marco",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        required=True,
        ondelete="restrict",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Ejecutivo de Cuenta",
        default=lambda self: self.env.user,
        help="Asesor responsable de este contrato marco",
    )
    suscripcion_ids = fields.One2many(
        comodel_name="publicidad.suscripcion",
        inverse_name="contrato_marco_id",
        string="Suscripciones",
        help="Historial de suscripciones bajo este contrato",
    )
