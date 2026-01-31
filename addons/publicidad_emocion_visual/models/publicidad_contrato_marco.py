from odoo import fields, models


class PublicidadContratoMarco(models.Model):
    _name = "publicidad.contrato.marco"
    _description = "Contrato Marco de Publicidad"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Referencia del Contrato", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Cliente", required=True, tracking=True
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string="Notas")
