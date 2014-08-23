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
import xml.etree.ElementTree

logging.basicConfig(level=0)
logger = logging.getLogger(__name__)
logger.setLevel(0)

try:
    logger.warning("Importing gnucash bindings.")
    logger.warning("Messages may be ignored until further notice.")
    import gnucash
except Exception as e:
    error = e
else:
    error = None
finally:
    logger.warning("Messages must now be heeded.")
    if error:
        if __name__ == "__main__":
            logger.fatal("Cannot import gnucash Python bindings.")
            exit(1)
        else:
            raise error

class GnucashSession(gnucash.Session):
    """Gnucash Session extended for us of with statement"""
    def __enter__(self):
        return self
    def __exit__(self, exc_t, exc_v, trace):
        self.destroy()

def get_budgets(input, year, month):
    tmpname = None
    with tempfile.NamedTemporaryFile(delete=False) as t:
        tmpname = t.name
        flag = False
        while True:
            line = input.readline()
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
                value = num * (-denom)
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
        starttime = endtime - datetime.timedelta(endtime.day - 0.5)
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
    oneday = datetime.timedelta(0.9)
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

def main(input,output,
         year=datetime.datetime.now().year,
         month=datetime.datetime.now().month):
    """
    filename = gnucash file path
    """
    root = get_root_account(input,output,year,month)
    basename = os.path.splitext(os.path.split(input.name)[-1])[0]
    output.write('<?xml version="1.0"?>\n')
    output.write('<?xml-stylesheet type="text/xsl" href="{:s}.xsl"?>\n'.format(basename))
    ET = xml.etree.ElementTree
    node = ET.Element('budget')
    node.append(root.get_xml())
    output.write(xml.etree.ElementTree.tostring(node))


def get_root_account(input,output,year,month):
    budgets = get_budgets(input,year,month)
    try:
        with GnucashSession(input.name) as session:
            root_account = session.get_book().get_root_account()
            balances = get_monthly_balances(root_account, year, month)
    except gnucash.gnucash_core.GnuCashBackendException:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False)
            with open(input.name) as f:
                tmp.write(f.read())
            tmp.close()
            with GnucashSession(tmp.name) as session:
                root_account = session.get_book().get_root_account()
                balances = get_monthly_balances(root_account, year, month)
        except:
            fmt = 'Cannot open gnucash file "{:s}".'
            msg = fmt.format(input.name)
            logger.fatal(msg)
            exit(1)
        finally:
            os.remove(tmp.name)
    root = Account()
    root.name = balances[1][0]
    root.guid = balances[0]
    for b in balances[1][-1]:
        root.add_child(create_accounts(b,budgets))
    return root

def create_accounts(balances, budgets):
    account = Account()
    account.name,account.is_flex,account.balance,children = balances[1]
    account.guid = balances[0]
    try:
        account.budget = budgets[account.guid]
    except KeyError:
        account.budget = 0.0
    for c in children:
        account.add_child(create_accounts(c,budgets))
    return account

class Account(object):
    def __init__(self):
        self.name = None
        self.balance = 0
        self.budget = 0
        self.children = []
        self._is_flex = False
    @property
    def level(self):
        try:
            return self.parent.level + 1
        except:
            return 0
    
    @property
    def is_flex(self):
        return self._is_flex or any([i.is_flex for i in self.children])
    @is_flex.setter
    def is_flex(self,value):
        self._is_flex = bool(value)
    @property
    def total_balance(self):
        """balance of self and all children"""
        return self.balance + sum([a.total_balance for a in self.children])
    @property
    def total_budget(self):
        """budget of self and all children"""
        return self.budget + sum([a.total_budget for a in self.children])
    
    def add_child(self, child):
        child.parent = self
        self.children.append(child)
    
    def get_xml(self):
        ET = xml.etree.ElementTree
        node = ET.Element('account')
        node.attrib['flex'] = str(1 * self.is_flex)
        node.attrib['level'] = str(self.level)
        for k,v in {
                    'name':self.name,
                    'guid':'guid'+self.guid,
                    'balance':str(round(self.total_balance,2)),
                    'budgeted':str(round(self.total_budget,2)),
                    }.iteritems():
            i = ET.SubElement(node,k)
            i.text = v

        # this element is duplicate information, but makes
        # the html generation easier
        def getElements(data, n):
            first_group = len(data) % n
            groups = [n] * int(len(data) / n)
            if first_group:
                groups.insert(0,first_group)
            i = 0
            for j in groups:
                yield data[i:i+j]
                i += j
        def format_currency(value):
            value = round(value,2)
            neg = value < 0
            string = '{:.2f}'.format(abs(value))
            whole,part = string.split('.')
            whole = ','.join(getElements(whole,3))
            if neg:
                whole = '-' + whole
            return '$' + whole + '.' + part
        def status(num,denom):
            if not denom:
                return 'bad'
            else:
                ratio = num / denom
                if ratio < 0.9:
                    return 'good'
                elif ratio < 1:
                    return 'ok'
                else:
                    return 'over'

        duplicate = ET.SubElement(node,'duplicate')
        for k,v in {
                   'flex':'flex' if self.is_flex else '',
                    'balance':format_currency(self.total_balance),
                    'budgeted':format_currency(self.total_budget),
                    'ratio':1e9 if not self.total_budget else round(self.total_balance / self.total_budget,6),
                    'status':status(self.total_balance,self.total_budget),
                    }.iteritems():
            i = ET.SubElement(duplicate,k)
            i.text = str(v)

        children = ET.SubElement(node,'children')
        map(lambda i: children.append(i.get_xml()),self.children)
        return node

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('INPUT',type=file,help='gnucash file path')
    parser.add_argument('-o','--output',type=argparse.FileType('w'),default=sys.stdout,help='report output file path')

    args = parser.parse_args()
    gnc_file = args.INPUT
    output = args.output
    

    main(gnc_file,output)


