from odoo import models, fields


class AccountMove(models.Model):
    _inherit = "account.move"

    suscripcion_ids = fields.One2many(
        comodel_name="publicidad.suscripcion",
        inverse_name="invoice_id",
        string="Suscripciones de publicidad",
    )

    def write(self, vals):
        res = super().write(vals)
        if "payment_state" in vals or "state" in vals:
            for move in self:
                if (
                    move.move_type == "out_invoice"
                    and move.state == "posted"
                    and move.payment_state == "paid"
                    and move.suscripcion_ids
                ):
                    move.suscripcion_ids._update_state_from_invoice()
        return res

