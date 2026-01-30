from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PublicidadSuscripcion(models.Model):
    _name = "publicidad.suscripcion"
    _description = "Suscripción de pauta publicitaria"
    _order = "fecha_inicio desc, id desc"

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        required=True,
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto / Variante",
        domain=[("detailed_type", "=", "service")],
        required=True,
    )

    duracion_meses = fields.Selection(
        selection=[
            ("3", "3 meses"),
            ("6", "6 meses"),
            ("12", "12 meses"),
            ("24", "24 meses"),
        ],
        string="Duración (meses)",
        required=True,
    )

    fecha_inicio = fields.Date(
        string="Fecha de inicio",
        required=True,
    )

    fecha_fin = fields.Date(
        string="Fecha de fin",
        compute="_compute_fecha_fin",
        store=True,
        readonly=True,
    )

    state = fields.Selection(
        selection=[
            ("borrador", "Borrador"),
            ("factura_pendiente", "Factura pendiente"),
            ("activa", "Activa"),
            ("vencida", "Vencida"),
        ],
        string="Estado",
        default="borrador",
        required=True,
        tracking=True,
    )

    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Factura",
        readonly=True,
        copy=False,
        domain=[("move_type", "=", "out_invoice")],
    )

    ubicacion = fields.Char(
        string="Ubicación",
        compute="_compute_ubicacion",
    )

    is_close_to_due = fields.Boolean(
        string="Próxima a vencer",
        compute="_compute_is_close_to_due",
        search="_search_is_close_to_due",
    )

    def _search_is_close_to_due(self, operator, value):
        if operator not in ("=", "!="):
            raise NotImplementedError(_("Operación no soportada para búsqueda de próximas a vencer"))

        today = fields.Date.context_today(self)
        limit_date = today + relativedelta(days=15)

        # Logic: is_close_to_due is True if:
        # fecha_fin AND state in ('activa', 'factura_pendiente') AND today <= fecha_fin <= limit_date

        domain_true = [
            ("fecha_fin", "!=", False),
            ("state", "in", ("activa", "factura_pendiente")),
            ("fecha_fin", ">=", today),
            ("fecha_fin", "<=", limit_date),
        ]

        if (operator == "=" and value) or (operator == "!=" and not value):
            return domain_true
        else:
            # Inverse of domain_true. A bit complex to negate via domain directly,
            # easier to return IDs or use a negating domain logic if possible.
            # However, for simplicity and performance in Odoo search methods returning a domain is preferred.
            # Negating (A AND B AND C AND D) is (!A OR !B OR !C OR !D).
            return [
                "|",
                "|",
                "|",
                ("fecha_fin", "=", False),
                ("state", "not in", ("activa", "factura_pendiente")),
                ("fecha_fin", "<", today),
                ("fecha_fin", ">", limit_date),
            ]

    def _get_duracion_meses_int(self):
        self.ensure_one()
        try:
            return int(self.duracion_meses or 0)
        except ValueError:
            return 0

    @api.depends("fecha_inicio", "duracion_meses")
    def _compute_fecha_fin(self):
        for rec in self:
            if rec.fecha_inicio and rec.duracion_meses:
                months = rec._get_duracion_meses_int()
                if months:
                    rec.fecha_fin = rec.fecha_inicio + relativedelta(months=months)
                else:
                    rec.fecha_fin = False
            else:
                rec.fecha_fin = False

    @api.depends("product_id")
    def _compute_ubicacion(self):
        for rec in self:
            location = False
            product = rec.product_id
            if product:
                for ptav in product.product_template_attribute_value_ids:
                    if ptav.attribute_id and ptav.attribute_id.name and ptav.attribute_id.name.lower() == "ubicación":
                        location = ptav.name
                        break
            rec.ubicacion = location

    @api.depends("fecha_fin", "state")
    def _compute_is_close_to_due(self):
        today = fields.Date.context_today(self)
        limit_date = today + relativedelta(days=15)
        for rec in self:
            rec.is_close_to_due = bool(
                rec.fecha_fin
                and rec.state in ("activa", "factura_pendiente")
                and today <= rec.fecha_fin <= limit_date
            )

    def action_confirm_and_invoice(self):
        """Crear factura de cliente y pasar a estado factura_pendiente."""
        for rec in self:
            if rec.state != "borrador":
                raise ValidationError(
                    _("Solo se pueden facturar suscripciones en estado borrador.")
                )
            if not rec.partner_id or not rec.product_id:
                raise ValidationError(
                    _("Debe seleccionar un cliente y un producto.")
                )

            # Obtener impuesto del 15% definido en datos del módulo
            tax_15 = self.env.ref(
                "publicidad_emocion_visual.publicidad_tax_15", raise_if_not_found=False
            )

            payment_term_immediate = self.env.ref(
                "account.account_payment_term_immediate", raise_if_not_found=False
            )

            product = rec.product_id
            name = product.get_product_multiline_description_sale() or product.display_name

            line_vals = {
                "product_id": product.id,
                "name": name,
                "quantity": 1.0,
                "price_unit": product.lst_price,
            }
            if tax_15:
                line_vals["tax_ids"] = [(6, 0, tax_15.ids)]

            move_vals = {
                "move_type": "out_invoice",
                "partner_id": rec.partner_id.id,
                "invoice_line_ids": [(0, 0, line_vals)],
            }
            if payment_term_immediate:
                move_vals["invoice_payment_term_id"] = payment_term_immediate.id

            move = self.env["account.move"].create(move_vals)

            rec.invoice_id = move
            rec.state = "factura_pendiente"

        return True

    def _update_state_from_invoice(self):
        """Actualizar estado según la factura asociada."""
        for rec in self:
            if (
                rec.invoice_id
                and rec.invoice_id.state == "posted"
                and rec.invoice_id.payment_state == "paid"
                and rec.state in ("borrador", "factura_pendiente")
            ):
                rec.state = "activa"

    @api.constrains("duracion_meses")
    def _check_duracion_meses(self):
        allowed = {"3", "6", "12", "24"}
        for rec in self:
            if rec.duracion_meses not in allowed:
                raise ValidationError(
                    _("Duración inválida. Solo se permiten 3, 6, 12 o 24 meses.")
                )

    @api.constrains("fecha_inicio", "fecha_fin")
    def _check_fechas(self):
        for rec in self:
            if rec.fecha_inicio and rec.fecha_fin and rec.fecha_inicio > rec.fecha_fin:
                raise ValidationError(
                    _("La fecha de inicio no puede ser posterior a la fecha de fin.")
                )

    @api.constrains("product_id", "fecha_inicio", "fecha_fin", "state")
    def _check_no_overbooking(self):
        for rec in self:
            if not (rec.product_id and rec.fecha_inicio and rec.fecha_fin):
                continue

            domain = [
                ("id", "!=", rec.id),
                ("product_id", "=", rec.product_id.id),
                ("state", "in", ["activa", "factura_pendiente"]),
                ("fecha_inicio", "<=", rec.fecha_fin),
                ("fecha_fin", ">=", rec.fecha_inicio),
            ]
            overlapping = self.search_count(domain)
            if overlapping:
                raise ValidationError(
                    _("Error: Esta pantalla ya está reservada para las fechas seleccionadas")
                )

