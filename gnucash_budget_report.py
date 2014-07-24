#!/usr/bin/env python2
"""gnucash_budget_report

get a nice report about the budget status.  I realize I should be able
to do this within gnucash, but this allows me much more flexibility, and
the ability to make a report automatically from the terminal.
"""

import logging
import argparse
import sys
import os
import time
import datetime

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(0)

try:
    logger.warning("Importing gnucash bindings.")
    logger.warning("Messages may be ignored until further notice.")
    import gnucash
except:
    success = False
else:
    success = True
finally:
    logger.warning("Messages must now be heeded.")
    if not success:
        logger.fatal("Cannot import gnucash Python bindings.")
        exit(1)


class Session(gnucash.Session):
    def __enter__(self):
        return self
    def __exit__(self, exc_t, exc_v, trace):
        self.destroy()

def get_budgets(filename):
    pass

def string_to_date(string):
    return datetime.datetime.strptime(string,'%Y-%m-%d')

def get_balances(account, starttime=None, endtime=None):
    if not endtime:
        endtime = datetime.datetime.now()
    if not starttime:
        starttime = endtime - datetime.timedelta(endtime.day)
    name = account.GetName()
    start_tuple = time.mktime(starttime.timetuple())
    end_tuple = time.mktime(endtime.timetuple())
    start_balance = account.GetBalanceAsOfDate(start_tuple).to_double()
    end_balance = account.GetBalanceAsOfDate(end_tuple).to_double()
    balance = end_balance - start_balance
    children = account.get_children_sorted()
    child_balance = dict(map(get_balances,children))
    return name, (balance, child_balance)

def get_monthly_balances(account, year, month):
    fmt = "{:4d}-{:02d}-{:02d}".format
    oneday = datetime.timedelta(1)
    end_date = string_to_date(fmt(year,month+1,1)) - oneday
    start_date = string_to_date(fmt(year,month,1)) - oneday
    return get_balances(account,start_date,end_date)


def main(filename,
         year=datetime.datetime.now().year,
         month=datetime.datetime.now().month):
    """
    filename = gnucash file path
    """
    try:
        with Session(filename) as session:
            import pdb; pdb.set_trace()
            root_account = session.get_book().get_root_account()
            balances = get_monthly_balances(root_account, year, month)
    except gnucash.gnucash_core.GnuCashBackendException:
        fmt = 'Cannot open gnucash file "{:s}".'
        msg = fmt.format(filename)
        logger.fatal(msg)
        exit(1)
    budgets = get_budgets(filename)
    import pdb; pdb.set_trace()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('INPUT',help='gnucash file path')

    args = parser.parse_args()
    filename = args.INPUT
    

    main(filename)


