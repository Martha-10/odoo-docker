from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PublicidadSuscripcion(models.Model):
    _name = "publicidad.suscripcion"
    _description = "Suscripción de pauta publicitaria"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "fecha_inicio desc, id desc"

    # 1.1 Identificación
    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nuevo"),
        tracking=True,
    )

    # 1.2 Bloque "Quién"
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        required=True,
        tracking=True,
    )
    contrato_marco_id = fields.Many2one(
        comodel_name="publicidad.contrato.marco",
        string="Contrato Marco",
        domain="[('partner_id', '=', partner_id)]",
        help="Permite agrupar múltiples suscripciones bajo un mismo contrato",
    )
    # Deprecated: Kept for backward compatibility
    contrato_marco = fields.Char(string="Contrato Marco (Deprecated)")
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Ejecutivo de Cuenta",
        default=lambda self: self.env.user,
        tracking=True,
    )

    # 1.3 Bloque "Dónde / Qué"
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Espacio Publicitario",
        domain=[("type", "=", "service")],
        required=True,
        tracking=True,
    )

    # Campos relacionados a producto (copia para historial o visualización)
    centro_comercial = fields.Selection(
        related="product_id.centro_comercial",
        string="Centro Comercial",
        readonly=False,
        store=True,
    )
    ubicacion_macro = fields.Selection(
        related="product_id.ubicacion_macro",
        string="Ubicación Macro",
        readonly=False,
        store=True,
    )
    ubicacion_detalle = fields.Char(
        string="Ubicación Detalle",
        compute="_compute_ubicacion_detalle",
        store=True,
        readonly=False,
    )
    # Deprecated: Kept for backward compatibility with old views during upgrade
    ubicacion = fields.Char(
        string="Ubicación (Deprecated)",
        compute="_compute_ubicacion_deprecated",
    )
    formato_id = fields.Selection(
        related="product_id.formato_id",
        string="Formato",
        readonly=False,
        store=True,
    )
    tipo_contenido = fields.Selection(
        related="product_id.tipo_contenido",
        string="Tipo de Contenido",
        readonly=False,
        store=True,
    )

    # 1.4 Bloque "Vigencia y Finanzas"
    duracion_meses = fields.Selection(
        selection=[
            ("3", "3 meses"),
            ("6", "6 meses"),
            ("12", "12 meses"),
            ("24", "24 meses"),
        ],
        string="Duración (meses)",
        required=True,
        tracking=True,
    )
    precio_mensual = fields.Monetary(
        string="Precio Mensual",
        currency_field="currency_id",
        tracking=True,
    )
    valor_total = fields.Monetary(
        string="Valor Total",
        compute="_compute_valor_total",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )

    metodo_pago = fields.Selection(
        selection=[
            ("contado", "Contado"),
            ("anticipo_saldo", "Anticipo + Saldo"),
            ("cuotas", "Cuotas"),
        ],
        string="Método de Pago",
        default="contado",
        required=True,
    )
    porcentaje_anticipo = fields.Float(
        string="% Anticipo",
        default=0.0,
    )
    monto_anticipo = fields.Monetary(
        string="Monto Anticipo",
        compute="_compute_monto_anticipo",
        store=True,
        currency_field="currency_id",
    )

    fecha_inicio = fields.Date(
        string="Fecha de inicio",
        required=True,
        default=fields.Date.context_today,
    )
    fecha_fin = fields.Date(
        string="Fecha de fin",
        compute="_compute_fecha_fin",
        store=True,
        readonly=True,
    )

    # 1.5 Estados y Flujo
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("confirmed", "Confirmado"),
            ("active", "En Exhibición"),
            ("paused", "Pausada"),
            ("expired", "Vencida"),
            ("cancel", "Cancelada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
        group_expand="_expand_states",
    )
    estado_arte = fields.Selection(
        selection=[
            ("pending", "Pendiente de Arte"),
            ("approved", "Arte Aprobado"),
            ("published", "En Exhibición"),
        ],
        string="Estado Arte",
        default="pending",
        tracking=True,
    )

    # Campos legacy/compatibilidad (se mantienen si se usan, o se adaptan)
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Factura",
        readonly=True,
        copy=False,
    )

    # --- LOGICA ---

    @api.model
    def create(self, vals):
        if vals.get("name", "Nuevo") == "Nuevo":
            # Formato: SUB / [Cliente] / [Referencia del Producto]
            partner_name = "Cliente"
            product_ref = "Producto"
            
            if "partner_id" in vals:
                partner = self.env["res.partner"].browse(vals["partner_id"])
                partner_name = partner.name or "S/C"
            
            if "product_id" in vals:
                 prod = self.env["product.product"].browse(vals["product_id"])
                 product_ref = prod.name or "S/P"

            vals["name"] = f"SUB / {partner_name} / {product_ref}"
        
        return super().create(vals)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.precio_mensual = self.product_id.lst_price
            # Los computed/related se actualizan solos, pero ubicacion detalle necesita trigger si vacio
            if not self.ubicacion_detalle:
                self.ubicacion_detalle = self.product_id.basic_ubicacion_detalle

    @api.depends("product_id")
    def _compute_ubicacion_detalle(self):
        for rec in self:
            if not rec.ubicacion_detalle and rec.product_id:
                 rec.ubicacion_detalle = rec.product_id.basic_ubicacion_detalle

    @api.depends("ubicacion_macro", "ubicacion_detalle")
    def _compute_ubicacion_deprecated(self):
        for rec in self:
            rec.ubicacion = f"{rec.ubicacion_macro or ''} - {rec.ubicacion_detalle or ''}"

    @api.depends("duracion_meses", "precio_mensual")
    def _compute_valor_total(self):
        for rec in self:
            try:
                months = int(rec.duracion_meses or 0)
            except ValueError:
                months = 0
            rec.valor_total = rec.precio_mensual * months

    @api.depends("valor_total", "porcentaje_anticipo", "metodo_pago")
    def _compute_monto_anticipo(self):
        for rec in self:
            if rec.metodo_pago in ["anticipo_saldo", "cuotas"] or rec.porcentaje_anticipo > 0:
                rec.monto_anticipo = rec.valor_total * (rec.porcentaje_anticipo / 100.0)
            else:
                rec.monto_anticipo = 0.0

    @api.depends("fecha_inicio", "duracion_meses")
    def _compute_fecha_fin(self):
        for rec in self:
            if rec.fecha_inicio and rec.duracion_meses:
                try:
                    months = int(rec.duracion_meses)
                    rec.fecha_fin = rec.fecha_inicio + relativedelta(months=months)
                except ValueError:
                    rec.fecha_fin = False
            else:
                rec.fecha_fin = False
    
    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).state.selection]

    # --- ACCIONES Y VALIDACIONES ---

    def action_confirm(self):
        for rec in self:
            rec.state = "confirmed"
             # 2.3 Anticipo 100%
            if rec.porcentaje_anticipo == 100.0:
                 pass
            
            # 2.2 Validación de Estado Técnico del Activo
            # Validar que el producto esté operativo. Asumimos x_estado_tecnico en el template
            if rec.product_id and rec.product_id.product_tmpl_id.x_estado_tecnico != 'operativo':
                 status_label = dict(rec.product_id.product_tmpl_id._fields['x_estado_tecnico'].selection).get(rec.product_id.product_tmpl_id.x_estado_tecnico)
                 raise ValidationError(_(
                     "Acción denegada: El activo %(product)s no puede ser reservado porque su estado actual es %(status)s. "
                     "Motivo: El equipo requiere intervención técnica antes de volver a ser comercializado."
                 ) % {'product': rec.product_id.name, 'status': status_label})

            # 2.1 Validación de Stock de Tiempo (Disponibilidad por cantidad)
            if rec.product_id and rec.fecha_inicio and rec.fecha_fin:
                # Contar suscripciones activas/confirmadas que se solapan
                domain = [
                    ('product_id', '=', rec.product_id.id),
                    ('state', 'in', ['confirmed', 'active']),
                    ('id', '!=', rec.id),
                    ('fecha_inicio', '<=', rec.fecha_fin),
                    ('fecha_fin', '>=', rec.fecha_inicio),
                ]
                overlapping_count = self.search_count(domain)
                
                # Obtener stock disponible (asumiendo que es un producto storable)
                # Si es servicio, debería tener una restricción custom o usarse qty_available si se gestiona
                # El requerimiento dice "Si existen 15 unidades...". Usaremos virtual_available o qty_available.
                # Para ser seguros, usaremos qty_available (Cantidad a mano/real).
                available_qty = rec.product_id.qty_available
                
                # Si es un servicio, qty_available suele ser 0 a menos que se configure. 
                # Si el usuario usa stock real, debe ser Storable.
                # Permitiremos verificar si available_qty > 0. Si es 0, asumimos sin limite O limite 1?
                # Regla: "Si existen 15 unidades...". Asumimos que el producto TIENE stock configurado.
                
                if available_qty > 0 and (overlapping_count + 1) > available_qty:
                     raise ValidationError(_(
                        "No es posible confirmar: No hay disponibilidad suficiente del bien para ese periodo. "
                        "(Capacidad Total: %(cap)s, Ocupado: %(occ)s, Solicitado: 1)"
                    ) % {
                        'cap': available_qty,
                        'occ': overlapping_count,
                    })
                elif available_qty == 0 and rec.product_id.type == 'product':
                     # Si es almacenable y tiene 0 stock
                     raise ValidationError(_("No hay stock disponible de este producto."))
                
                # Si es servicio (type='service') y qty=0, quizá deberíamos permitir o bloquear.
                # El requerimiento dice "Bienes físicos reales...". Asumimos Productos Almacenables.

    def action_active(self):
        for rec in self:
            # 2.1 Validación de Arte
            if rec.estado_arte == "pending":
                raise ValidationError(_("No se puede iniciar la exhibición sin el arte aprobado. Por favor apruebe el arte primero."))
            rec.state = "active"

    def action_pause(self):
        self.write({"state": "paused"})

    def action_cancel(self):
        self.write({"state": "cancel"})
    
    def action_draft(self):
        self.write({"state": "draft"})
    
    # --- ARTE ---
    def action_approve_art(self):
        self.write({"estado_arte": "approved"})

