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
        comodel_name="contrato.marco",
        string="Contrato Marco",
        domain="[('partner_id', '=', partner_id)]",
        ondelete="set null",
        help="Contrato marco que agrupa esta suscripción",
    )
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

    # === ATRIBUTOS FÍSICOS DEL ACTIVO (READONLY - Desde Inventario) ===
    formato = fields.Char(
        string="Formato",
        compute="_compute_technical_specs",
        store=True,
        readonly=True,
        help="Formato del activo físico (extraído del inventario)",
    )
    tamano = fields.Char(
        string="Tamaño",
        compute="_compute_technical_specs",
        store=True,
        readonly=True,
        help="Dimensiones del activo físico (extraído del inventario)",
    )
    
    # === VARIABLES DE NEGOCIO Y SERVICIO (EDITABLES) ===
    tipo_contenido = fields.Selection(
        selection=[
            ("estatico", "Estático"),
            ("video", "Video"),
        ],
        string="Tipo de Contenido",
        required=True,
        default="estatico",
        tracking=True,
        help="Tipo de contenido a exhibir. Video tiene cargo adicional.",
    )
    centro_comercial = fields.Selection(
        selection=[
            ("viva", "Viva"),
            ("buenavista", "Buenavista"),
            ("mallplaza", "Mallplaza"),
            ("unico", "Unico"),
            ("plaza_central", "Plaza Central"),
        ],
        string="Centro Comercial",
        required=True,
        tracking=True,
        help="Sede donde se exhibirá el activo",
    )
    ubicacion_macro = fields.Selection(
        selection=[
            ("fachada", "Fachada"),
            ("entrada", "Entrada"),
            ("pasillo", "Pasillo"),
            ("plazoleta", "Plazoleta de Comidas"),
        ],
        string="Ubicación Macro",
        required=True,
        tracking=True,
        help="Espacio de exhibición contratado",
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
        compute="_compute_precio_mensual",
        store=True,
        readonly=True,
        currency_field="currency_id",
        tracking=True,
        help="Precio base + extras de atributos (Video, etc.)",
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
    numero_cuotas = fields.Integer(
        string="Número de Cuotas",
        default=1,
        help="Cantidad de cuotas para pago fraccionado",
    )
    valor_cuota = fields.Monetary(
        string="Valor por Cuota",
        compute="_compute_valor_cuota",
        store=True,
        currency_field="currency_id",
        help="Monto de cada cuota (calculado automáticamente)",
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
    anticipo_recibido = fields.Boolean(
        string="Anticipo Recibido",
        default=False,
        tracking=True,
        groups="publicidad_emocion_visual.group_publicidad_finanzas,base.group_erp_manager",
        help="Marcar cuando el anticipo ha sido pagado (Solo Finanzas/Admin)",
    )
    # Overrides manuales para el Administrador
    manual_surcharge_ubicacion = fields.Monetary(
        string="Recargo Manual Ubicación",
        groups="base.group_erp_manager",
        currency_field="currency_id",
        help="Permite forzar un recargo de ubicación si falla la lectura del inventario",
    )
    manual_surcharge_contenido = fields.Monetary(
        string="Recargo Manual Contenido",
        groups="base.group_erp_manager",
        currency_field="currency_id",
        help="Permite forzar un recargo de contenido si falla la lectura del inventario",
    )
    saldo_restante = fields.Monetary(
        string="Saldo Restante",
        compute="_compute_saldo_restante",
        store=True,
        currency_field="currency_id",
        help="Saldo después de descontar el anticipo (valor_total - monto_anticipo)",
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
            ("waiting_payment", "Esperando Pago"),
            ("confirmed", "Confirmado"),
            ("active", "En Exhibición"),
            ("paused", "Pausada"),
            ("expired", "Vencida"),
            ("cancel", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
        group_expand="_expand_states",
    )
    estado_arte = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("received", "Recibido"),
            ("approved", "Aprobado"),
        ],
        string="Estado del Arte",
        default="pending",
        tracking=True,
        help="Estado de aprobación del contenido publicitario",
    )

    # Campos de Permisos para la Vista (Evita errores de uid_has_groups)
    is_finanzas_or_admin = fields.Boolean(compute="_compute_permissions")
    is_operaciones_or_higher = fields.Boolean(compute="_compute_permissions")

    @api.depends_context('uid')
    def _compute_permissions(self):
        """Calcula permisos dinámicos para la interfaz de usuario"""
        for rec in self:
            rec.is_finanzas_or_admin = self.env.user.has_group('publicidad_emocion_visual.group_publicidad_finanzas') or self.env.user.has_group('base.group_erp_manager')
            rec.is_operaciones_or_higher = self.env.user.has_group('publicidad_emocion_visual.group_publicidad_operaciones') or rec.is_finanzas_or_admin

    # Campos legacy/compatibilidad (se mantienen si se usan, o se adaptan)
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Factura",
        readonly=True,
        copy=False,
    )

    # --- LOGICA ---

    @api.onchange("partner_id", "product_id", "ubicacion_macro")
    def _onchange_name_auto(self):
        """Genera título dinámico: SUB / [Cliente] / [Activo] / [Ubicación]"""
        for rec in self:
            partner_name = rec.partner_id.name or "Cliente"
            product_ref = rec.product_id.name or "Activo"
            ubicacion = dict(rec._fields['ubicacion_macro'].selection).get(rec.ubicacion_macro, "") if rec.ubicacion_macro else ""
            
            if ubicacion:
                rec.name = f"SUB / {partner_name} / {product_ref} / {ubicacion}"
            else:
                rec.name = f"SUB / {partner_name} / {product_ref}"

    @api.model
    def create(self, vals):
        if vals.get("name", "Nuevo") == "Nuevo":
            partner_name = "Cliente"
            product_ref = "Activo"
            ubicacion = ""
            
            if "partner_id" in vals:
                partner = self.env["res.partner"].browse(vals["partner_id"])
                partner_name = partner.name or "S/C"
            
            if "product_id" in vals:
                prod = self.env["product.product"].browse(vals["product_id"])
                product_ref = prod.name or "S/P"
            
            if "ubicacion_macro" in vals and vals["ubicacion_macro"]:
                ubicacion_dict = dict(self._fields['ubicacion_macro'].selection)
                ubicacion = ubicacion_dict.get(vals["ubicacion_macro"], "")
            
            if ubicacion:
                vals["name"] = f"SUB / {partner_name} / {product_ref} / {ubicacion}"
            else:
                vals["name"] = f"SUB / {partner_name} / {product_ref}"
        
        return super().create(vals)

    @api.depends("product_id")
    def _compute_technical_specs(self):
        """Extrae atributos técnicos readonly desde attribute_line_ids del inventario"""
        for rec in self:
            rec.formato = ""
            rec.tamano = ""
            
            if not rec.product_id or not rec.product_id.product_tmpl_id:
                continue
                
            # Buscar en las líneas de atributos del template
            for attr_line in rec.product_id.product_tmpl_id.attribute_line_ids:
                attr_name = attr_line.attribute_id.name.lower() if attr_line.attribute_id.name else ""
                
                if "formato" in attr_name:
                    # Obtener el valor específico para esta variante
                    for ptav in rec.product_id.product_template_attribute_value_ids:
                        if ptav.attribute_id == attr_line.attribute_id:
                            rec.formato = ptav.product_attribute_value_id.name
                            break
                            
                elif "tamaño" in attr_name or "tamano" in attr_name:
                    for ptav in rec.product_id.product_template_attribute_value_ids:
                        if ptav.attribute_id == attr_line.attribute_id:
                            rec.tamano = ptav.product_attribute_value_id.name
                            break

    @api.depends("product_id", "tipo_contenido", "centro_comercial", "ubicacion_macro", "duracion_meses")
    def _compute_precio_mensual(self):
        """Motor de precios 100% reactivo con escala de prestigio y consulta dinámica al inventario"""
        for rec in self:
            if not rec.product_id:
                rec.precio_mensual = 0.0
                continue
            
            # ===== 1. PRECIO BASE DEL ACTIVO =====
            # Incluye el list_price + extras de Tamaño y Formato ya configurados en la variante
            base_price = rec.product_id.lst_price
            attribute_extras = rec.product_id.price_extra if hasattr(rec.product_id, 'price_extra') else 0.0
            
            # ===== 2. ESCALA DE PRESTIGIO (CENTRO COMERCIAL) =====
            prestige_surcharge = {
                'buenavista': 1500000.0,  # Prestigio Diamante
                'viva': 1000000.0,         # Prestigio Oro
                'mallplaza': 500000.0,     # Prestigio Plata
                'unico': 0.0,              # Base
                'plaza_central': 0.0,      # Base
            }.get(rec.centro_comercial, 0.0)
            
            # ===== 3. CONSULTA DINÁMICA AL INVENTARIO (PRICE_EXTRA) =====
            ubicacion_extra = 0.0
            contenido_extra = 0.0
            
            if rec.product_id.product_tmpl_id:
                # Buscar en los atributos del template para extraer price_extra
                for ptav in rec.product_id.product_template_attribute_value_ids:
                    if not ptav.attribute_id or not ptav.product_attribute_value_id:
                        continue
                    
                    attr_name = ptav.attribute_id.name.lower().strip()
                    value_name = ptav.product_attribute_value_id.name.lower().strip()
                    
                    # UBICACIÓN: Buscar atributo 'ubicacion' exactamente
                    if attr_name == "ubicacion" or "ubicación" in attr_name:
                        if rec.ubicacion_macro:
                            ubicacion_selected = rec.ubicacion_macro.lower().strip()
                            # Verificar si el valor del atributo coincide con la selección
                            if ubicacion_selected in value_name or value_name in ubicacion_selected:
                                ubicacion_extra += ptav.price_extra
                                break  # Solo tomar el primero que coincida
                    
                    # TIPO DE CONTENIDO: Buscar atributo 'tipo' o 'contenido'
                    if "tipo" in attr_name or "contenido" in attr_name:
                        if rec.tipo_contenido == "video" and "video" in value_name:
                            contenido_extra += ptav.price_extra
            
            # ===== 4. CÁLCULO FINAL =====
            # FÓRMULA: base + prestige + (ubicacion_extra o manual) + (contenido_extra o manual)
            final_ubicacion = rec.manual_surcharge_ubicacion if rec.manual_surcharge_ubicacion > 0 else ubicacion_extra
            final_contenido = rec.manual_surcharge_contenido if rec.manual_surcharge_contenido > 0 else contenido_extra
            
            rec.precio_mensual = (
                base_price +           # Precio base del producto
                prestige_surcharge +   # Plus por Centro Comercial
                final_ubicacion +      # Extra por Ubicación
                final_contenido        # Extra por Video
            )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Pre-carga inteligente al seleccionar activo"""
        if self.product_id:
            # Pre-cargar centro comercial si hay atributo de ubicación
            if self.product_id.product_tmpl_id:
                for attr_line in self.product_id.product_tmpl_id.attribute_line_ids:
                    attr_name = attr_line.attribute_id.name.lower() if attr_line.attribute_id.name else ""
                    
                    if "ubicacion" in attr_name or "centro" in attr_name:
                        for ptav in self.product_id.product_template_attribute_value_ids:
                            if ptav.attribute_id == attr_line.attribute_id:
                                val_name = ptav.product_attribute_value_id.name.lower()
                                
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
                                break
    
    @api.onchange("tipo_contenido")
    def _onchange_tipo_contenido(self):
        """Ajuste automático de precio si se selecciona Video"""
        if self.product_id and self.tipo_contenido == "video":
            # Precio base + precio extra de la variante
            base_price = self.product_id.lst_price
            extra_price = self.product_id.price_extra if hasattr(self.product_id, 'price_extra') else 0.0
            self.precio_mensual = base_price + extra_price
        elif self.product_id:
            # Volver al precio base si cambia a estático
            self.precio_mensual = self.product_id.lst_price

    @api.depends("valor_total", "porcentaje_anticipo", "numero_cuotas")
    def _compute_valor_cuota(self):
        """Calcula el valor de cada cuota sobre el SALDO RESTANTE (valor_total - monto_anticipo)"""
        for rec in self:
            if rec.numero_cuotas and rec.numero_cuotas > 0:
                # Calcular saldo restante en línea para evitar dependencias circulares
                monto_anticipo = rec.valor_total * (rec.porcentaje_anticipo / 100.0) if rec.porcentaje_anticipo > 0 else 0.0
                saldo_pendiente = rec.valor_total - monto_anticipo
                rec.valor_cuota = saldo_pendiente / rec.numero_cuotas
            else:
                rec.valor_cuota = 0.0

    @api.depends("duracion_meses", "precio_mensual")
    def _compute_valor_total(self):
        for rec in self:
            try:
                months = int(rec.duracion_meses or 0)
            except ValueError:
                months = 0
            rec.valor_total = rec.precio_mensual * months

    @api.depends("valor_total", "monto_anticipo")
    def _compute_saldo_restante(self):
        """Calcula el saldo restante después de descontar el anticipo"""
        for rec in self:
            rec.saldo_restante = rec.valor_total - rec.monto_anticipo

    @api.depends("valor_total", "porcentaje_anticipo")
    def _compute_monto_anticipo(self):
        """Calcula el monto del anticipo basado en el porcentaje"""
        for rec in self:
            # FÓRMULA EXACTA: monto_anticipo = valor_total * (porcentaje_anticipo / 100)
            # Si porcentaje_anticipo es 0, el monto DEBE ser 0
            if rec.porcentaje_anticipo > 0:
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
        """Validaciones estrictas de disponibilidad"""
        for rec in self:
            if rec.state not in ['confirmed', 'active']:
                continue

            if not rec.product_id:
                continue

            # 1. VALIDACIÓN DE STOCK FÍSICO
            if rec.product_id.qty_available == 0:
                raise ValidationError(_(
                    "Activo Fuera de Servicio: %(product)s no tiene stock disponible. "
                    "Se encuentra en mantenimiento o fuera de bodega."
                ) % {'product': rec.product_id.display_name})

            # 2. VALIDACIÓN DE ESTADO TÉCNICO
            if hasattr(rec.product_id.product_tmpl_id, 'x_estado_tecnico') and \
               rec.product_id.product_tmpl_id.x_estado_tecnico != 'operativo':
                status_label = dict(rec.product_id.product_tmpl_id._fields['x_estado_tecnico'].selection).get(
                    rec.product_id.product_tmpl_id.x_estado_tecnico, 'No Operativo'
                )
                raise ValidationError(_(
                    "Acción Bloqueada: El activo %(product)s no puede ser reservado porque su estado actual es %(status)s. "
                    "Motivo: El equipo requiere intervención técnica."
                ) % {'product': rec.product_id.display_name, 'status': status_label})

            # 3. VALIDACIÓN DE AGENDA (Conflicto de Fechas)
            if rec.fecha_inicio and rec.fecha_fin:
                domain_search = [
                    ('product_id', '=', rec.product_id.id),
                    ('state', 'in', ['confirmed', 'active']),
                    ('id', '!=', rec.id),
                    ('fecha_inicio', '<=', rec.fecha_fin),
                    ('fecha_fin', '>=', rec.fecha_inicio),
                ]
                conflict = self.search(domain_search, limit=1)
                
                if conflict:
                    start_str = conflict.fecha_inicio.strftime('%d/%m/%Y')
                    end_str = conflict.fecha_fin.strftime('%d/%m/%Y')
                    contrato_ref = conflict.contrato_marco_id.name if conflict.contrato_marco_id else "Sin Contrato"
                    
                    raise ValidationError(_(
                        "Bloqueo de Agenda: El activo %(product)s ya está asignado al contrato %(contrato)s "
                        "del %(start)s al %(end)s."
                    ) % {
                        'product': rec.product_id.display_name,
                        'contrato': contrato_ref,
                        'start': start_str,
                        'end': end_str,
                    })

    def action_request_approval(self):
        """Solicita aprobación de finanzas y notifica"""
        for rec in self:
            rec.state = "waiting_payment"
            # Notificación en el chatter
            rec.message_post(
                body=_("Solicitud de Aprobación: El Asesor ha enviado esta suscripción para validación de pago."),
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

    def action_confirm(self):
        """Confirma la suscripción (Normalmente por Finanzas)"""
        for rec in self:
            rec.state = "confirmed"
            rec.message_post(body=_("Suscripción Confirmada: El pago ha sido validado."))

    def action_active(self):
        """Activa la suscripción con validaciones estrictas"""
        for rec in self:
            # VALIDACIÓN 1: Anticipo debe estar recibido
            if rec.monto_anticipo > 0 and not rec.anticipo_recibido:
                raise ValidationError(_(
                    "Acción Bloqueada: No se puede iniciar la pauta sin confirmar la recepción del anticipo. "
                    "Por favor, verifique el pago con contabilidad."
                ))
            
            # VALIDACIÓN 2: Arte debe estar aprobado
            if rec.estado_arte != "approved":
                raise ValidationError(_(
                    "Control de Calidad: El arte aún no ha sido aprobado. "
                    "Debe cambiar el Estado del Arte a 'Aprobado' antes de poner la suscripción en exhibición."
                ))
            
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

