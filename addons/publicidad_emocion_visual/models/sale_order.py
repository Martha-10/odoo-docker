from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            order._create_publicidad_subscriptions()
        return res

    def _create_publicidad_subscriptions(self):
        self.ensure_one()
        Subscription = self.env["publicidad.suscripcion"]
        ContratoMarco = self.env["contrato.marco"]

        # Ensure we have a Master Contract (Contrato Marco) for this client
        contrato = ContratoMarco.search([("partner_id", "=", self.partner_id.id)], limit=1)
        if not contrato:
            contrato = ContratoMarco.create({
                "name": f"MC-{self.partner_id.name}-{fields.Date.today()}",
                "partner_id": self.partner_id.id,
                "user_id": self.user_id.id,
            })

        for line in self.order_line:
            # Only create for 'product' type products (Storable / Assets)
            if line.product_id.type == 'product':
                Subscription.create({
                    "partner_id": self.partner_id.id,
                    "contrato_marco_id": contrato.id,
                    "product_id": line.product_id.id,
                    "fecha_inicio": line.x_pauta_inicio or fields.Date.today(),
                    "duracion_meses": line.x_pauta_duracion or '12',
                    "user_id": self.user_id.id,
                    "sale_line_id": line.id,
                })


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_pauta_inicio = fields.Date(string="Inicio Pauta")
    x_pauta_duracion = fields.Selection(
        selection=[
            ("3", "3 meses"),
            ("6", "6 meses"),
            ("12", "12 meses"),
            ("24", "24 meses"),
        ],
        string="Duración Pauta",
        default="12",
    )

    @api.onchange('product_id')
    def _onchange_product_id_price_integrity(self):
        if self.product_id:
            self.price_unit = self.product_id.lst_price

    @api.constrains('product_id', 'price_unit')
    def _check_price_integrity(self):
        for line in self:
            if line.product_id and line.price_unit != line.product_id.lst_price:
                line.price_unit = line.product_id.lst_price
