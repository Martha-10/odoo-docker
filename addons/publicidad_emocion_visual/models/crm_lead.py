from odoo import models, fields, api


class CrmLead(models.Model):
    _inherit = "crm.lead"

    product_id = fields.Many2one(
        "product.product",
        string="Activo Publicitario",
        domain=[("type", "=", "product")],
        help="Activo publicitario de interés capturado desde el formulario web.",
    )

    def action_new_quotation(self):
        action = super(CrmLead, self).action_new_quotation()
        if self.product_id:
            # Ensure the context has the product_id to be used in the sale order line
            action['context'].update({
                'default_order_line': [(0, 0, {
                    'product_id': self.product_id.id,
                    'product_uom_qty': 1.0,
                })]
            })
        return action
