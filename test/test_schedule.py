
# For latest 'tests.json' file, see:
#  web:  https://github.com/schyntax/schyntax/blob/master/tests.json
#  raw:  https://raw.githubusercontent.com/schyntax/schyntax/master/tests.json
# Might be nice to have a better way to get an updated version of that file 
# without committing it to this repository too.

import os
import json
import datetime

import pytest

from schyntax import Schedule, SchyntaxParseException, InvalidScheduleException


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


@pytest.mark.parametrize('fmt', [
    # empty
    "",
    " ",
    "{}",
])
def test_invalid_schedule_exception(fmt):
    with pytest.raises(InvalidScheduleException):
        Schedule(fmt)


@pytest.mark.parametrize('fmt', [
    # bad expression name (at least)
    "foo",
    "foo()",
    "foo(*)",
    
    # bad parens
    "(",
    ")",
    "()",
    "{",
    "}",
    
    # unexpected symbols
    "/",
    ":",
    '"',
    
    # bare attribs
    "1",
    "*",
    "monday",
    
    # incomplete expressions
    "minute",
    "minute(",
    "minute()",
    "minute(5",
    "minute(5..",
    "minute(5..)",
    "minute(5%",
    "minute(5%)",
    "minute(!",
    "minute(!%",
    "minute(!%)",
    
    
    # wrong attribute types
    "minute(monday)",
    "minute(4/1)",
    "dayofweek(1..tuesday % wednesday)",
    
    # bad attribute values
    "minute(foo)",
    
    # attribute out of legal range
    "minute(-1)",
    "minute(60)",
    "minute(999999999999999999999999999999999999999)",
    "dayofweek(8)",
    
    # bad year usage
    "date(2015/1/1 .. 4/15)",       # mix of partial and full dates
    "date(2015/1/1 .. 2014/1/1)",   # absolute dates out of order
    
    # years with no Feb 29 (2100 will not - as currently defined - be a leap year)
    "date(2015/2/29)",
    "date(2100/2/29)",
    
    # otherwise bogus
    "minute 5",
    
])
def test_parse_exception(fmt):
    with pytest.raises(SchyntaxParseException):
        Schedule(fmt)

