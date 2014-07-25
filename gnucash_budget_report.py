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
import tempfile
from xml.dom import minidom

logging.basicConfig(level=0)
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

def get_budgets(filename, year, month):
    tmpname = None
    with open(filename) as f:
        with tempfile.NamedTemporaryFile(delete=False) as t:
            tmpname = t.name
            flag = False
            while True:
                line = f.readline()
                if not line:
                    break
                if 'gnc:budget' in line:
                    flag = not '/gnc:budget' in line
                if (flag or line.startswith('<?xml')
                         or 'gnc-v2' in line
                         or 'xmlns' in line
                         or '/gnc:budget' in line):
                    t.write(line)
    logger.info('start parse xml')
    xmldoc = minidom.parse(tmpname)
    logger.info('end parse xml')
    budget_start_date = xmldoc.getElementsByTagName('gdate')[0].firstChild.data
    budget_start_date = string_to_date(budget_start_date)
    request_date = ymd_tuple_to_date((year,month,1))
    slot_number = int((request_date - budget_start_date).days * 12/365.25)
    slots = xmldoc.getElementsByTagName('slot')
    guids = [s.getElementsByTagName('slot:key')[0].firstChild.data for s in slots]
    budget = []
    for s in slots:
        sub_slots = s.getElementsByTagName('slot')
        keys = [ss.getElementsByTagName('slot:key')[0].firstChild.data for ss in sub_slots]
        keys = map(int,keys)
        try:
            index = keys.index(slot_number)
        except ValueError:
            value = 0.0
        else:
            value = sub_slots[index].getElementsByTagName('slot:value')[0].firstChild.data
            num,denom = map(float,value.split('/'))
            if denom < 0:
                value = num * denom
            else:
                value = num / denom
        budget.append(value)
    budget = dict(zip(guids,budget))
    return budget


def ymd_tuple_to_date(t):
    return string_to_date('{:04d}-{:02d}-{:02d}'.format(*t))
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
    guid = account.GetGUID().to_string()
    try:
        flex = 'flex' in account.GetNotes()
    except TypeError:
        flex = False
    children = account.get_children_sorted()
    child_balance = list(map(lambda i: get_balances(i,starttime,endtime),children))
    return guid, (name, flex, balance, child_balance)


def get_monthly_balances(account, year, month):
    fmt = "{:4d}-{:02d}-{:02d}".format
    oneday = datetime.timedelta(1)
    end_date = string_to_date(fmt(year,month+1,1)) - oneday
    start_date = string_to_date(fmt(year,month,1)) - oneday
    return get_balances(account,start_date,end_date)


def plain_text(balances, budgets, prefix = ''):
    name,flex,balance,children = balances[1]
    name = prefix + name
    guid = balances[0]
    try:
        budget = budgets[guid]
    except KeyError:
        budget = 0.0
    if flex:
        flex = '*'
    else:
        flex = ' '
    string = '{:30s}{:1s}: {:12.2f}   of {:12.2f}\n'.format(name,flex,balance,budget)
    for c in children:
        string += plain_text(c,budgets,prefix=prefix+' ')
    return string

def main(filename,
         year=datetime.datetime.now().year,
         month=datetime.datetime.now().month):
    """
    filename = gnucash file path
    """
    budgets = get_budgets(filename,year,month)
    try:
        with Session(filename) as session:
            root_account = session.get_book().get_root_account()
            balances = get_monthly_balances(root_account, year, month)
    except gnucash.gnucash_core.GnuCashBackendException:
        fmt = 'Cannot open gnucash file "{:s}".'
        msg = fmt.format(filename)
        logger.fatal(msg)
        exit(1)
    for b in balances[1][-1]:
        sys.stdout.write(plain_text(b,budgets))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('INPUT',help='gnucash file path')

    args = parser.parse_args()
    filename = args.INPUT
    

    main(filename)


