#!/usr/bin/env python
import argparse
import os
import logging
import sys
import subprocess

DIR = os.path.dirname(__file__)
os.chdir(DIR)

def update_report(INPUT,output,force=False):
    try:
        update_input = os.lstat(INPUT).st_mtime
    except:
        logging.fatal('File "{:s}" unaccesible.'.format(INPUT))
        exit(1)
    try:
        update_output = os.lstat(output).st_mtime
        output = open(output,'w')
    except OSError:
        update_output = 0
        output = open(output,'w')
    except TypeError:
        update_output = 0
        output = sys.stdout
    if update_input > update_output or force:
        from gnucash_budget_report import main
        main(INPUT,output)
    else:
        print('Report already updated')

def update_script():
    results = subprocess.call('git pull -f')
    


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('INPUT', help='gnucash file')
    parser.add_argument('-o','--output',default=None, help='output xml file')
    parser.add_argument('--update', action='store_true', help='update script files before generating report')
    parser.add_argument('-f','--force', action='store_true', help='force update report')

    args = parser.parse_args()
    if args.update:
        update_script()
    update_report(args.INPUT, args.output, force=args.force)
else:
    logging.warning('This file, {:s}, not intended to be imported!'.format(__file__))
