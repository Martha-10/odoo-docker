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
