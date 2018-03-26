# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import odoo.addons.decimal_precision as dp


class BudgetLine(models.Model):
    _inherit = 'crossovered.budget.lines'

    analytic_line_ids = fields.One2many(
        'account.analytic.line', 'budget_line_id', 'Analytic Lines')
    commitment_amount = fields.Float(
        'Commitment Amount', digits=0,
        compute="_get_commitment_amounts")
    available_amount = fields.Float(
        'Available Amount', digits=0,
        compute="_get_commitment_amounts")

    @api.one
    def _get_commitment_amounts(self):
        self.commitment_amount = self.with_context(commitment=True). \
            _prac_amt()[self.id]
        self.available_amount = self.planned_amount - self.commitment_amount

    @api.multi
    def _get_sql_query(self, analytic_account_id, date_from, date_to,
                       acc_ids, commitment=False):
        """
        If computing commitment, search lines with commitment account,
        else with general account.
        """
        sql_string = "SELECT SUM(amount) " \
                     "FROM account_analytic_line " \
                     "WHERE account_id=%s " \
                     "AND (date between to_date(%s,'yyyy-mm-dd') " \
                     "AND to_date(%s,'yyyy-mm-dd')) " + \
                     "AND " + \
                     ("%s " % "commitment_account_id"
                      if self._context.get('commitment')
                      else "general_account_id") + \
                     "=ANY(%s)"
        sql_args = (analytic_account_id, date_from, date_to, acc_ids)
        return sql_string, sql_args

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None,
                   orderby=False, lazy=True):
        fields_to_compute = []
        for field in ('commitment_amount', 'available_amount',
                      'practical_amount', 'theoritical_amount'):
            if field in fields:
                fields.remove(field)
                fields_to_compute.append(field)
        res = super(BudgetLine, self).read_group(
            domain, fields, groupby, offset, limit, orderby, lazy)
        if fields_to_compute:
            for group in res:
                if group.get('__domain'):
                    line_infos = self.search_read(group['__domain'],
                                                  fields_to_compute)
                    for field in fields_to_compute:
                        group[field] = sum([l[field] for l in line_infos])
        return res

    @api.multi
    def action_open_analytic_lines(self):
        self.ensure_one()
        return {
            'name': _('Analytic Lines'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.analytic.line',
            'target': 'new',
            'domain': [('id', 'in', self.analytic_line_ids._ids)],
            'context': self._context,
        }


class BudgetPositionCommitmentLimit(models.Model):
    _name = 'account.budget.post.commitment_limit'
    _description = 'Budgetary Position Commitment Limit'
    _rec_name = 'budget_post_id'

    budget_post_id = fields.Many2one(
        'account.budget.post', 'Budgetary Position',
        required=True, index=True, ondelete='cascade')
    user_id = fields.Many2one(
        'res.users', 'User', required=True, index=True)
    amount_limit = fields.Float(
        'Commitment Amount Limit', digits=dp.get_precision('Account'),
        required=True)

    @api.constrains('amount_limit', 'user_id')
    def check_amount_limit_inferior_global_limit(self):
        if self.user_id.commitment_global_limit and \
                self.amount_limit > self.user_id.commitment_global_limit:
            raise UserError(_("You cannot define a budget post commitment"
                              "limit superior to the global limit of "
                              "this user"))


class BudgetPosition(models.Model):
    _inherit = 'account.budget.post'

    commitment_limit_ids = fields.One2many(
        'account.budget.post.commitment_limit', 'budget_post_id',
        'Commitment Limits')