# Copyright (c) 2023, 杨嘉祥 and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate, datetime, get_first_day, get_last_day, formatdate
from erpnext.accounts.report.trial_balance.trial_balance import (
    get_opening_balances,
    filter_accounts,
)

from erpnext.accounts.utils import get_balance_on


def execute(filters=None):
  validate_filters(filters)
  columns = get_columns(filters)

  settings = frappe.get_single("Profit and Loss Statement Settings")

  data = list(map(lambda d: frappe._dict({
      "idx": d.idx,
      "label": d.label,
      "indent": d.indent,
      "calc_type": d.calc_type,
      "calc_sources": d.calc_sources,
  }), settings.items))

  data = get_data(data, filters)
  if filters.month:
    data = get_data_yearly(data, filters)

  currency = filters.presentation_currency or frappe.get_cached_value(
      "Company", filters.company, "default_currency"
  )

  return columns, data


def validate_filters(filters):
  if not filters.fiscal_year:
    frappe.throw(_("Fiscal Year {0} is required").format(filters.fiscal_year))

  fiscal_year = frappe.db.get_value(
      "Fiscal Year", filters.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
  )
  if not fiscal_year:
    frappe.throw(
        _("Fiscal Year {0} does not exist").format(filters.fiscal_year))
  else:
    filters.year_start_date = getdate(fiscal_year.year_start_date)
    filters.year_end_date = getdate(fiscal_year.year_end_date)

  if filters.month:
    filters.from_date = get_first_day(datetime.date(
        year=cint(filters.fiscal_year), month=cint(filters.month), day=1))
    filters.to_date = get_last_day(datetime.date(
        year=cint(filters.fiscal_year), month=cint(filters.month), day=1))
  else:
    filters.from_date = filters.year_start_date
    filters.to_date = filters.year_end_date

  # if not filters.from_date:
  # 	filters.from_date = filters.year_start_date

  # if not filters.to_date:
  # 	filters.to_date = filters.year_end_date

  filters.from_date = getdate(filters.from_date)
  filters.to_date = getdate(filters.to_date)

  if filters.from_date > filters.to_date:
    frappe.throw(_("From Date cannot be greater than To Date"))

  if (filters.from_date < filters.year_start_date) or (filters.from_date > filters.year_end_date):
    frappe.msgprint(
        _("From Date should be within the Fiscal Year. Assuming From Date = {0}").format(
            formatdate(filters.year_start_date)
        )
    )

    filters.from_date = filters.year_start_date

  if (filters.to_date < filters.year_start_date) or (filters.to_date > filters.year_end_date):
    frappe.msgprint(
        _("To Date should be within the Fiscal Year. Assuming To Date = {0}").format(
            formatdate(filters.year_end_date)
        )
    )
    filters.to_date = filters.year_end_date


def filter_accounts(accounts):
  parent_children_map = {}
  accounts_by_num = {}
  for d in accounts:
    accounts_by_num[d.account_number] = d
    parent_children_map.setdefault(d.parent_number or None, []).append(d)

  return accounts, accounts_by_num, parent_children_map


def get_data(data, filters):
  accounts = frappe.db.sql(
      """select acc.name, acc.account_number, parent.account_number as parent_number,
    acc.parent_account, acc.account_name,
    acc.root_type, acc.report_type, acc.lft, acc.rgt
    from `tabAccount` acc
    left join `tabAccount` parent on parent.name = acc.parent_account
    where acc.company=%s and acc.root_type in ('Income', 'Expense') order by acc.lft""",
      filters.company,
      as_dict=True,
  )
  if not accounts:
    return None

  accounts, accounts_by_num, parent_children_map = filter_accounts(accounts)

  opening_balances = get_opening_balances(filters)

  for d in accounts:
    closing_balance = get_balance_on(d.name, filters.to_date)
    acc_opening_balances = opening_balances.get(d.name, {})
    if d.root_type == 'Expense':
      d.opening_balance = acc_opening_balances.get(
          "opening_debit", 0) - acc_opening_balances.get("opening_credit", 0)
      d.closing_balance = closing_balance
    else:
      d.opening_balance = acc_opening_balances.get(
          "opening_credit", 0) - acc_opening_balances.get("opening_debit", 0)
      d.closing_balance = 0 - closing_balance
    accounts_by_num[d.account_number].update({
        "opening_balance": d.opening_balance,
        "closing_balance": d.closing_balance,
    })

  for d in reversed(accounts):
    if d.parent_number and accounts_by_num[d.parent_number]:
      accounts_by_num[d.parent_number]["opening_balance"] += d["opening_balance"]

  rows_map = {}
  for d in data:
    rows_map[cstr(d.idx)] = {
        "name": d.name,
        "opening_balance": 0.0,
        "closing_balance": 0.0,
    }
    if d.calc_type and d.calc_sources and d.calc_type == "Closing Balance":
      d.opening_balance = d.closing_balance = 0.0
      d.calc_sources = list(filter(None, d.calc_sources.split(",")))
      d.accounts = []
      for account_number in d.calc_sources:
        minus = False
        if account_number.startswith("-"):
          account_number = account_number[1:]
          minus = True
        account = accounts_by_num.get(account_number)
        if account:
          d.accounts.append({
              "direction": (-1 if minus else 1),
              "name": account.name,
              "account_number": account.account_number,
              "account_name": account.account_name,
              "opening_balance": account.opening_balance,
              "closing_balance": account.closing_balance,
          })
        d.opening_balance += (-1 if minus else 1) * accounts_by_num.get(
            account_number, {}).get("opening_balance", 0.0)
        d.closing_balance += (-1 if minus else 1) * accounts_by_num.get(
            account_number, {}).get("closing_balance", 0.0)
        d.amount = d.get("closing_balance", 0.0) - \
            d.get("opening_balance", 0.0)
      rows_map[cstr(d.idx)].update({
          "opening_balance": d.opening_balance,
          "closing_balance": d.closing_balance,
          "amount": d.amount,
      })

  for d in data:
    if d.calc_type and d.calc_sources and d.calc_type == "Calculate Rows":
      d.opening_balance = d.closing_balance = 0.0
      d.calc_sources = list(filter(None, d.calc_sources.split(",")))
      d.rows = []
      for idx in d.calc_sources:
        minus = False
        if idx.startswith("-"):
          idx = idx[1:]
          minus = True
        idx = cint(idx)
        row = rows_map.get(cstr(idx))
        d.opening_balance += (-1 if minus else 1) * \
            row.get("opening_balance", 0.0)
        d.closing_balance += (-1 if minus else 1) * \
            row.get("closing_balance", 0.0)
        d.amount = d.get("closing_balance", 0.0) - \
            d.get("opening_balance", 0.0)
        d.rows.append({
            "direction": (-1 if minus else 1),
            "idx": idx,
            "name": row.get("name"),
            "opening_balance": row.get("opening_balance"),
            "closing_balance": row.get("closing_balance"),
        })
      rows_map[cstr(d.idx)].update({
          "opening_balance": d.opening_balance,
          "closing_balance": d.closing_balance,
          "amount": d.amount,
      })

  return data


def get_data_yearly(data, filters):
  filters = filters.copy()
  filters.from_date = filters.year_start_date
  filters.to_date = filters.year_end_date
  accounts = frappe.db.sql(
      """select acc.name, acc.account_number, parent.account_number as parent_number,
    acc.parent_account, acc.account_name,
    acc.root_type, acc.report_type, acc.lft, acc.rgt
    from `tabAccount` acc
    left join `tabAccount` parent on parent.name = acc.parent_account
    where acc.company=%s and acc.root_type in ('Income', 'Expense') order by acc.lft""",
      filters.company,
      as_dict=True,
  )
  if not accounts:
    return None

  accounts, accounts_by_num, parent_children_map = filter_accounts(accounts)

  opening_balances = get_opening_balances(filters)

  for d in accounts:
    closing_balance = get_balance_on(d.name, filters.to_date)
    acc_opening_balances = opening_balances.get(d.name, {})
    if d.root_type == 'Expense':
      d.opening_balance = acc_opening_balances.get(
          "opening_debit", 0) - acc_opening_balances.get("opening_credit", 0)
      d.closing_balance = closing_balance
    else:
      d.opening_balance = acc_opening_balances.get(
          "opening_credit", 0) - acc_opening_balances.get("opening_debit", 0)
      d.closing_balance = 0 - closing_balance
    accounts_by_num[d.account_number].update({
        "opening_balance": d.opening_balance,
        "closing_balance": d.closing_balance,
    })

  for d in reversed(accounts):
    if d.parent_number:
      accounts_by_num[d.parent_number]["opening_balance"] += d["opening_balance"]

  rows_map = {}
  for d in data:
    rows_map[cstr(d.idx)] = {
        "name": d.name,
        "opening_balance": 0.0,
        "closing_balance": 0.0,
    }
    if d.calc_type and d.calc_sources and d.calc_type == "Closing Balance":
      d.yearly_opening_balance = d.yearly_closing_balance = 0.0
      # d.calc_sources = list(filter(None, d.calc_sources.split(",")))
      d.accounts = []
      for account_number in d.calc_sources:
        minus = False
        if account_number.startswith("-"):
          account_number = account_number[1:]
          minus = True
        # account = accounts_by_num.get(account_number)
        # if account:
        #   d.accounts.append({
        #       "direction": (-1 if minus else 1),
        #       "name": account.name,
        #       "account_number": account.account_number,
        #       "account_name": account.account_name,
        #       "opening_balance": account.opening_balance,
        #       "closing_balance": account.closing_balance,
        #   })
        d.yearly_opening_balance += (-1 if minus else 1) * accounts_by_num.get(
            account_number, {}).get("opening_balance", 0.0)
        d.yearly_closing_balance += (-1 if minus else 1) * accounts_by_num.get(
            account_number, {}).get("closing_balance", 0.0)
        d.yearly_amount = d.yearly_closing_balance - d.yearly_opening_balance
      rows_map[cstr(d.idx)].update({
          "opening_balance": d.yearly_opening_balance,
          "closing_balance": d.yearly_closing_balance,
          "amount": d.yearly_amount,
      })

  for d in data:
    if d.calc_type and d.calc_sources and d.calc_type == "Calculate Rows":
      d.yearly_opening_balance = d.yearly_closing_balance = 0.0
      # d.calc_sources = list(filter(None, d.calc_sources.split(",")))
      d.rows = []
      for idx in d.calc_sources:
        minus = False
        if idx.startswith("-"):
          idx = idx[1:]
          minus = True
        idx = cint(idx)
        row = rows_map.get(cstr(idx))
        d.yearly_opening_balance += (-1 if minus else 1) * \
            row.get("opening_balance", 0.0)
        d.yearly_closing_balance += (-1 if minus else 1) * \
            row.get("closing_balance", 0.0)
        d.yearly_amount = d.yearly_closing_balance - d.yearly_opening_balance
        # d.rows.append({
        #     "direction": (-1 if minus else 1),
        #     "idx": idx,
        #     "name": row.get("name"),
        #     "opening_balance": row.get("opening_balance"),
        #     "closing_balance": row.get("closing_balance"),
        # })
      rows_map[cstr(d.idx)].update({
          "opening_balance": d.yearly_opening_balance,
          "closing_balance": d.yearly_closing_balance,
          "amount": d.yearly_amount,
      })

  return data


def get_columns(filters):
  columns = [
      {
          "label": "项目",
          "fieldname": "label",
          "fieldtype": "Data",
          "width": 300,
      },
      {
          "label": "行次",
          "fieldname": "idx",
          "fieldtype": "Int",
          "width": 60,
      },
      {
          "label": "期初数",
          "fieldname": "opening_balance",
          "fieldtype": "Currency",
          "width": 120,
          "hidden": 1,
      },
      {
          "label": "金额",
          "fieldname": "amount",
          "fieldtype": "Currency",
          "width": 120,
      },
      {
          "label": "期末数",
          "fieldname": "closing_balance",
          "fieldtype": "Currency",
          "width": 120,
          "hidden": 1,
      },
  ]

  if filters.month:
    columns.extend([
        {
            "label": "年初数",
            "fieldname": "yearly_opening_balance",
            "fieldtype": "Currency",
            "width": 120,
            "hidden": 1,
        },
        {
            "label": "年合计",
            "fieldname": "yearly_amount",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "年末数",
            "fieldname": "yearly_closing_balance",
            "fieldtype": "Currency",
            "width": 120,
            "hidden": 1,
        },
    ])

  return columns
