# noinspection PyUnresolvedReferences
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = "Purchase Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request Name', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    requester_id = fields.Many2one('res.users', string='Requester', default=lambda self: self.env.user, tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, tracking=True)
    dateline_date = fields.Date(string='Deadline', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To Approve'),
        ('approved', 'Approved'),
        ('purchasing', 'Purchasing'),
        ('done', 'Done'),
        ('cancel', 'Cancel')
    ], string='Status', default='draft', tracking=True)

    note = fields.Text(string='Note')
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency')

    line_ids = fields.One2many('purchase.request.line', 'request_id', string='Detail Request')

    total_amount = fields.Monetary(string='Total Amount', compute='_compute_total_amount', store=True)
    is_over_budget = fields.Boolean(string='Over Budget', compute='_compute_is_over_budget')
    purchase_count = fields.Integer(string='Purchase Count', compute='_compute_purchase_count')

    approved_date = fields.Datetime(string='Approved Date', readonly=True, copy=False)

    @api.depends('line_ids.subtotal')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.line_ids.mapped('subtotal'))

    @api.depends('total_amount')
    def _compute_is_over_budget(self):
        for record in self:
            record.is_over_budget = record.total_amount > 50000000

    def _compute_purchase_count(self):
        for record in self:
            record.purchase_count = self.env['purchase.order'].search_count([('request_id', '=', record.id)])

    def action_submit(self):
        for record in self:
            if not record.line_ids:
                raise UserError(_("Please add at least one product line before submitting for approval."))
            record.state = 'to_approve'

    def action_approve(self):
        for record in self:
            record.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now()
            })

    def action_create_po(self):
        for record in self:
            lines_by_vendor = {}
            for line in record.line_ids:
                if not line.vendor_id:
                    raise UserError(_("Please select a suggested vendor for product %s.") % line.product_id.display_name)

                if line.vendor_id not in lines_by_vendor:
                    lines_by_vendor[line.vendor_id] = []
                lines_by_vendor[line.vendor_id].append(line)

            for vendor, lines in lines_by_vendor.items():
                po_vals = {
                    'partner_id': vendor.id,
                    'request_id': record.id,
                    'order_line': []
                }
                for line in lines:
                    po_vals['order_line'].append((0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.description or line.product_id.name,
                        'product_qty': line.qty,
                        'product_uom': line.product_uom_id.id,
                        'price_unit': line.price_unit,
                        'date_planned': line.need_by_date or record.dateline_date or fields.Datetime.now(),
                    }))
                self.env['purchase.order'].create(po_vals)

            record.state = 'purchasing'

    def action_done(self):
        for record in self:
            record.state = 'done'

    def action_cancel(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_("You cannot cancel a completed request."))
            record.state = 'cancel'

    def action_draft(self):
        for record in self:
            record.state = 'draft'

    @api.constrains('request_date', 'dateline_date')
    def _check_date(self):
        for record in self:
            if record.request_date and record.dateline_date and record.dateline_date < record.request_date:
                raise ValidationError(_("The deadline cannot be earlier than the request date."))

    @api.constrains('is_over_budget', 'note')
    def _check_budget_note(self):
        for record in self:
            if record.is_over_budget and not record.note:
                raise ValidationError(_("This request is over budget! Please provide an explanation note."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.request.seq') or _('New')
        return super(PurchaseRequest, self).create(vals_list)

    def unlink(self):
        for record in self:
            if record.state not in ('draft', 'cancel'):
                raise UserError(_("You can only delete requests that are in Draft or Cancelled state."))
        return super(PurchaseRequest, self).unlink()

    @api.onchange('requester_id')
    def _onchange_requester_id(self):
        if self.requester_id:
            employee = self.env['hr.employee'].search([('user_id', '=', self.requester_id.id)], limit=1)
            if employee:
                self.department_id = employee.department_id.id

    @api.onchange('dateline_date')
    def _onchange_dateline_date(self):
        if self.dateline_date and self.request_date:
            delta = self.dateline_date - self.request_date
            if delta.days < 3:
                return {
                    'warning': {
                        'title': _("Date Warning"),
                        'message': _("The deadline is very close to the request date.")
                    }
                }

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Related Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('request_id', '=', self.id)],
            'context': {'default_request_id': self.id},
        }


class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'

    request_id = fields.Many2one('purchase.request', string='Purchase Request', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description')

    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    qty = fields.Float(string='Quantity', default=1.0, required=True)
    price_unit = fields.Float(string='Unit Price')
    available_qty = fields.Float(string='Available Quantity')

    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal')
    need_by_date = fields.Date(string='Need By Date')
    vendor_id = fields.Many2one('res.partner', string='Suggested Vendor')
    company_id = fields.Many2one('res.company')

    _sql_constraints = [
        ('unique_product_request', 'UNIQUE(request_id, product_id)', 'You cannot add the same product multiple times in a single request.')
    ]

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.price_unit

    @api.constrains('qty')
    def _check_qty(self):
        for line in self:
            if line.qty <= 0:
                raise ValidationError(_("Quantity must be strictly positive (> 0)."))

    @api.constrains('need_by_date')
    def _check_need_by_date(self):
        for line in self:
            if line.need_by_date and line.request_id.request_date and line.need_by_date < line.request_id.request_date:
                raise ValidationError(_("The 'Need by Date' cannot be earlier than the Request Date."))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.display_name
            self.product_uom_id = self.product_id.uom_po_id
            self.price_unit = self.product_id.standard_price
            self.available_qty = self.product_id.qty_available

    @api.onchange('qty', 'price_unit')
    def _onchange_qty_price(self):
        if self.qty > self.available_qty and self.available_qty > 0:
            return {
                'warning': {
                    'title': _("Inventory Warning"),
                    'message': _("The requested quantity exceeds the currently available stock (%s)!") % self.available_qty
                }
            }


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    request_id = fields.Many2one('purchase.request', string='Source Request', readonly=True)