
# noinspection PyUnresolvedReferences
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = "Purchase Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string = 'Request Name', required = True, copy=False, readonly=True, default=lambda self: _('New'))
    requester_id = fields.Many2one('res.users', default=lambda self: self.env.user, tracking = True)
    department_id = fields.Many2one('hr.department', tracking=True)
    request_date = fields.Date(string ='Request Date', default=fields.Date.context_today, tracking=True)
    dateline_date = fields.Date(string ='Deadline', tracking = True)

    state = fields.Selection([('draft', 'Draft'),
                              ('to_approve', 'To Approve'),
                              ('approved', 'Approved'),
                              ('purchasing', 'Purchasing'),
                              ('done', 'Done'),
                              ('cancel', 'Cancel')])

    note = fields.Text(string = 'Note')
    approved_by = fields.Many2one('res.users', string = 'Approved By', readonly=True, copy = False)
    company_id = fields.Many2one('res.company')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency')

    line_ids = fields.One2many('purchase.request.line', 'request_id', string = 'Detail Request')

    total_amount=fields.Monetary(string = 'Total Amount', compute = '_compute_total_amount', store=True)
    is_over_budget = fields.Boolean(string = 'Over Budget', compute = '_compute_is_over_budget')
    purchase_count = fields.Integer(string = 'Purchase Count', compute='_compute_purchase_count')

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
            record.purchase_count = 0

    def action_submit(self):
        for record in self:
            if not record.line_ids:
                raise UserError(_("Add at least one line before submitting for approval"))
            record.state = 'to_approve'
    def action_approve(self):
        for record in self:
            if any(line.qty <= 0 for line in record.line_ids):
                raise UserError(_("Must have a quantity > 0"))

            record.write({
                'state': 'approved',
                'approved_by':self.env.user.id,
                'approved_date': fields.Datetime.now()
            })
    def action_create_po(self):
        for record in self:
            record.state = 'purchasing'

    def action_done(self):
        for record in self:
            record.state = 'done'

    def action_cancel(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_("Cannot cancel a completed request"))
            record.state = 'cancel'

    def action_draft(self):
        for record in self:
            record.state = 'draft'

    @api.constrains('request_date', 'dateline_date')
    def _check_date(self):
        for record in self:
            if record.request_date and record.dateline_date and record.dateline_date < record.request_date:
                raise ValidationError(_("Deadline cannot be earlier than Request Date"))

    @api.constrains('is_over_budget', 'note')
    def _check_budget_note(self):
        for record in self:
            if record.is_over_budget and not record.note:
                raise ValidationError(_("Over Budget!!!, Leave a note"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_core('purchase.request.seq') or _('New')
        return super(PurchaseRequest, self).create(vals_list)

    def unlink(self):
        for record in self:
            if record.state not in ('draft', 'cancel'):
                raise UserError(_("Can only delete requests in Draft or Cancel"))

        return super(PurchaseRequest, self).unlink()

class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'

    request_id = fields.Many2one('purchase.request', string='Purchase Request', ondelete='cascade')
    product_id = fields.Many2one('product.product', string ='Product', required = True)
    description = fields.Char(string='Description')

    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    qty = fields.Float(string ='Quantity', default=1.0, required =True)
    price_unit = fields.Float(string='Unit Price')
    available_qty = fields.Float(string = 'Available Quantity')

    subtotal = fields.Float(string = 'Subtotal', compute = '_compute_subtotal')
    need_by_date = fields.Date(string = 'Need By Date')
    vendor_id = fields.Many2one('res.partner', string = 'Suggested Vendor')
    company_id = fields.Many2one('res.company')

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.product_uom_id = self.product_id.uom_po_id
            self.price_unit = self.product_id.standard_price