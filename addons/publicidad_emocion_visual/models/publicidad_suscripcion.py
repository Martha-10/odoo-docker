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
        string="Activo Publicitario",
        # Domain removed to restore visibility.
        # domain=[("type", "=", "product")],
        required=True,
        tracking=True,
    )

    # Campos relacionados a producto (Sincronización Total con Atributos)
    centro_comercial = fields.Selection(
        selection=[
            ("viva", "Viva"),
            ("buenavista", "Buenavista"),
            ("mallplaza", "Mallplaza"),
            ("unico", "Unico"),
            ("plaza_central", "Plaza Central"),
        ],
        string="Centro Comercial",
        store=True,
        readonly=False, # Editable por el usuario
        tracking=True,
    )
    ubicacion_macro = fields.Char(
        string="Ubicación Macro",
        compute="_compute_attributes",
        store=True,
    )
    # ubicacion_detalle removed as requested
    
    formato_id = fields.Char(
        string="Formato",
        compute="_compute_attributes",
        store=True,
    )
    tamano = fields.Char(
        string="Tamaño",
        compute="_compute_attributes",
        store=True,
    )
    tipo_contenido = fields.Char(
        string="Tipo de Contenido",
        compute="_compute_attributes",
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

    @api.onchange("partner_id", "product_id")
    def _onchange_name_auto(self):
        for rec in self:
            partner_name = rec.partner_id.name or "Cliente"
            product_ref = rec.product_id.name or "Activo"
            rec.name = f"SUB / {partner_name} / {product_ref}"

    @api.model
    def create(self, vals):
        if vals.get("name", "Nuevo") == "Nuevo":
            # Recalcular nombre si viene como Nuevo para asegurar consistencia
            partner_name = "Cliente"
            product_ref = "Activo"
            
            if "partner_id" in vals:
                partner = self.env["res.partner"].browse(vals["partner_id"])
                partner_name = partner.name or "S/C"
            
            if "product_id" in vals:
                 prod = self.env["product.product"].browse(vals["product_id"])
                 product_ref = prod.name or "S/P"

            vals["name"] = f"SUB / {partner_name} / {product_ref}"
        
        return super().create(vals)

    @api.depends("product_id")
    def _compute_attributes(self):
        for rec in self:
            # Reset values for computed fields
            # Notice centro_comercial is NOT computed here anymore to allow editing.
            rec.ubicacion_macro = ""
            rec.formato_id = ""
            rec.tamano = ""
            rec.tipo_contenido = ""
            
            if rec.product_id:
                # Iterar sobre los valores de atributos del producto variante
                for ptav in rec.product_id.product_template_attribute_value_ids:
                    # ptav.attribute_id.name -> Nombre del atributo (Ej: 'Formato')
                    # ptav.name -> Valor del atributo (Ej: 'Valla')
                    attr_name = ptav.attribute_id.name.lower() if ptav.attribute_id.name else ""
                    val_name = ptav.name
                    
                    if "formato" in attr_name:
                        rec.formato_id = val_name
                    elif "tamaño" in attr_name or "tamano" in attr_name:
                        rec.tamano = val_name
                    elif "contenido" in attr_name:
                        rec.tipo_contenido = val_name
                    elif "ubicación" in attr_name or "ubicacion" in attr_name:
                         # Si es macro ubicacion (Pasillo, Entrada etc)
                         if val_name in ["Fachada", "Entrada", "Pasillo", "Plazoleta de Comidas"]:
                            rec.ubicacion_macro = val_name
                         else:
                            # Intento asignar a macro de todas formas
                            rec.ubicacion_macro = val_name

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.precio_mensual = self.product_id.lst_price
            
            # Pre-carga inteligente de Centro Comercial
            # Buscamos en los atributos si hay algo que coincida con las opciones
            for ptav in self.product_id.product_template_attribute_value_ids:
                val_name = ptav.name.lower()
                # Mapeo simple basado en las opciones del selection
                if "viva" in val_name:
                    self.centro_comercial = "viva"
                elif "buenavista" in val_name:
                    self.centro_comercial = "buenavista"
                elif "mallplaza" in val_name:
                    self.centro_comercial = "mallplaza"
                elif "unico" in val_name:
                    self.centro_comercial = "unico"
                elif "plaza" in val_name and "central" in val_name:
                    self.centro_comercial = "plaza_central"

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

    @api.constrains('state', 'product_id', 'fecha_inicio', 'fecha_fin')
    def _check_availability_constrains(self):
        for rec in self:
            if rec.state not in ['confirmed', 'active']:
                continue

            # 1. Estado Técnico
            if rec.product_id and rec.product_id.product_tmpl_id.x_estado_tecnico != 'operativo':
                 status_label = dict(rec.product_id.product_tmpl_id._fields['x_estado_tecnico'].selection).get(rec.product_id.product_tmpl_id.x_estado_tecnico)
                 raise ValidationError(_(
                     "Acción Bloqueada: El activo %(product)s no puede ser reservado porque su estado actual es %(status)s. "
                     "Motivo: El equipo requiere intervención técnica."
                 ) % {'product': rec.product_id.name, 'status': status_label})

            # 2. Cruce de Fechas / Stock
            domain_search = [
                ('product_id', '=', rec.product_id.id),
                ('state', 'in', ['confirmed', 'active']),
                ('id', '!=', rec.id),
                ('fecha_inicio', '<=', rec.fecha_fin),
                ('fecha_fin', '>=', rec.fecha_inicio),
            ]
            overlapping_count = self.search_count(domain_search)
            available_qty = rec.product_id.qty_available

            if available_qty > 0 and (overlapping_count + 1) > available_qty:
                 conflict = self.search(domain_search, limit=1)
                 start_str = conflict.fecha_inicio.strftime('%d/%m/%Y') if conflict else rec.fecha_inicio
                 end_str = conflict.fecha_fin.strftime('%d/%m/%Y') if conflict else rec.fecha_fin
                 
                 raise ValidationError(_(
                    "Acción Bloqueada: El equipo %(product)s ya está reservado del %(start)s al %(end)s.\n"
                    "(Capacidad Total: %(cap)s, Ocupado: %(occ)s)"
                ) % {
                    'product': rec.product_id.name,
                    'start': start_str,
                    'end': end_str,
                    'cap': available_qty,
                    'occ': overlapping_count,
                })
            elif available_qty == 0:
                 raise ValidationError(_("No hay stock disponible de este activo (0 unidades)."))

    def action_confirm(self):
        for rec in self:
            rec.state = "confirmed"
             # 2.3 Anticipo 100%
            if rec.porcentaje_anticipo == 100.0:
                 pass
            # Validation handled by constrains on state change

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

