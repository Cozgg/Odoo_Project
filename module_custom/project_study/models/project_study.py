from odoo import api, models, fields

class StudyTags(models.Model):
    _name = 'study.tags'
    _description = 'Study Tags'

    name = fields.Char(string = 'Tag Name', required = True)

class ProjectStudy(models.Model):
    _name = 'project.study'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Project Study'
    _order = 'date_deadline desc, create_date desc'

    name = fields.Char(string = 'Name', required = True, tracking=1)
    user_id = fields.Many2one('res.users', string = 'Assigned To', tracking=2)
    date_start = fields.Date(string = 'Start Date')
    date_end = fields.Date(string = 'End Date')
    date_deadline = fields.Date(string = 'DateLine', tracking=3)
    parent_id = fields.Many2one('project.study', string = 'Parent')
    tag_ids = fields.Many2many('study.tags', string = 'Tags')
    state = fields.Selection([('todo', 'To Do'), ('inprogress', 'In-progress'),
                              ('review', 'Review'), ('done', 'Done')], string = 'State', default = 'todo', tracking = 4)


def _notify_assigned_user(self):
    for rec in self:
        if rec.user_id and rec.user_id.email:
            rec.message_post(
                body=f"Task {rec.name} đã được giao cho bạn.",
                subject="Cập nhật người phụ trách",
                partner_ids=[rec.user_id.partner_id.id],
                subtype_xmlid='mail.mt_comment',
            )


@api.model_create_multi
def create(self, vals_list):
    records = super().create(vals_list)
    records.filtered('user_id')._notify_assigned_user()
    return records


def write(self, vals):
    res = super().write(vals)
    if 'user_id' in vals:
        self.filtered('user_id')._notify_assigned_user()
    return res