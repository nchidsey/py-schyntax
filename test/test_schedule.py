
# For latest 'tests.json' file, see:
#  web:  https://github.com/schyntax/schyntax/blob/master/tests.json
#  raw:  https://raw.githubusercontent.com/schyntax/schyntax/master/tests.json
# Might be nice to have a better way to get an updated version of that file 
# without committing it to this repository too.

import os
import json
import datetime

import pytest

from schyntax import Schedule


def _gather_cases():
    '''
    Returns list of test cases from the 'tests.json' file for the test below.
    '''
    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    
    with open("test/tests.json") as f:
        stuff = json.loads(f.read())
    
    checks = []
    
    for name, group in stuff.items():
        for check in group["checks"]:
            fmt = check["format"]
            date = datetime.datetime.strptime(check["date"], date_format)
            prev = datetime.datetime.strptime(check["prev"], date_format)
            next = datetime.datetime.strptime(check["next"], date_format)
            
            checks.append((fmt, date, prev, next))
    
    return checks


@pytest.mark.parametrize('fmt,date,prev,next', _gather_cases())
def test_json_data(fmt, date, prev, next):
    schedule = Schedule(fmt)
    assert next == schedule.next(date)
    assert prev == schedule.previous(date)

