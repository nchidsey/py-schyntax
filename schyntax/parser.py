# Note this is not the same AST parser as the reference Javascript or C#
#
# FIXME - dates are supposed to allow optional year in yyyy/m/d format
#
# FIXME - spec doesn't mention it (I think) but the code looks like it 
#         may allow "5.." as a range without second value
#
# INCOMPLETE - validation!  See Validator in C#. May want to do it in 
#         here if possible, or from the Schedule class

import re

from schyntax.exceptions import SchyntaxParseException, InvalidScheduleException
from schyntax.dateutil import get_days_in_month


# this eats an optional trailing comma, see elsewhere for whether this is legal
# note this strips space from the inner expression string, which the parser requires later
_expression_regex = re.compile(r'^\s*(\w+)\s*\(\s*([^)]*\s*)\)\s*,?\s*')

# capturing parens: 
#     '!', asterisk, first_value, '..'|'..<', second_value, mod_value
# this eats an optional trailing comma, it is not clear in the docs as
# of this time whether that is legal or if a final comma is disallowed.
# TODO - maybe make this multiline so it's not such a long line.
_argument_regex = re.compile(
    r'^\s*(!)?\s*(?:(\*)\s*|(\d+/\d+|-?\d+|\w+)\s*(?:(\.\.<?)\s*(\d+/\d+|-?\d+|\w+)\s*)?)(?:%\s*(\d+))?\s*,?\s*')


# Map of allowed expression "function" names to the internal string used by the parser
_expression_types = {
    's': 'seconds',
    'sec': 'seconds',
    'second': 'seconds',
    'seconds': 'seconds',
    'secondofminute': 'seconds',
    'secondsofminute': 'seconds',
    
    'm': 'minutes',
    'min': 'minutes',
    'minute': 'minutes',
    'minutes': 'minutes',
    'minuteofhour': 'minutes',
    'minutesofhour': 'minutes',
    
    'h': 'hours',
    'hour': 'hours',
    'hours': 'hours',
    'hourofday': 'hours',
    'hoursofday': 'hours',
    
    'day': 'dow',
    'days': 'dow',
    'dow': 'dow',
    'dayofweek': 'dow',
    'daysofweek': 'dow',
    
    'dom': 'dom',
    'dayofmonth': 'dom',
    'daysofmonth': 'dom',
    
    'date': 'dates',
    'dates': 'dates',
}

_day_of_week_literals = {
    'su': 1,
    'mo': 2,
    'tu': 3,
    'we': 4,
    'th': 5,
    'fr': 6,
    'sa': 7,
    
    'sun': 1,
    'mon': 2,
    'tue': 3,
    'wed': 4,
    'thu': 5,
    'fri': 6,
    'sat': 7,
    
    'sunday': 1,
    'monday': 2,
    'tuesday': 3,
    'wednesday': 4,
    'thursday': 5,
    'friday': 6,
    'saturday': 7,
    
    # special extra abbrevs
    'tues': 3,
    'thur': 5,
    'thurs': 5,
}


class Group(object):
    def __init__(self):
        # each of these is a list of Range instances
        self.dates = []
        self.dates_excluded = []
        self.days_of_month = []
        self.days_of_month_excluded = []
        self.days_of_week = []
        self.days_of_week_excluded = []
        self.hours = []
        self.hours_excluded = []
        self.minutes = []
        self.minutes_excluded = []
        self.seconds = []
        self.seconds_excluded = []
    

# Internal, used during parsing
class Argument(object):
    is_exclude = False
    
    is_wildcard = False
    
    start = None
    end = None      # None if not specified
    is_half_open = False
    
    mod = None      # None if not specified


# slightly differing from C# project. skipping "IsRange" and "HasInterval"
# Could add those as properties?
class Range(object):
    start = None
    end = None              # always non-none, even if no range specified (equal to start)
    is_half_open = False
    interval = None         # always non-none, even if no interval specified (assigned to 1)
    
    def __init__(self, start, end, is_half_open=False, interval=1):
        assert end is not None
        assert interval is not None
        
        self.start = start
        self.end = end
        self.is_half_open = is_half_open
        self.interval = interval
    
    def clone(self):
        return Range(self.start, self.end, self.is_half_open, self.interval)


class DateValue(object):
    # no year support yet   -- btw, both dates in range must have or not have a year, or it won't make sense
    #        also split ranges (start > end) are not allowed to have years
    month = None
    day = None
    
    def __init__(self, month, day):
        # note currently both month and day must be integers (not validated by type or value though)
        self.month = month
        self.day = day

    def __lt__(self, other):
        # FIXME - when adding years, change this or think about whether it is used correctly from the schedule code
        #         AT LEAST ensure both have years or both do not
        return self.month < other.month or (self.month == other.month and self.day < other.day)
        

def _validate_integer(expression_type, value, min, max, allow_negative):
    if min <= value <= max:
        return
    if value < 0 and allow_negative and min <= -value <= max:
        return
    
    #if allow_negative: perhaps to adjust the exception message?
    # note this appears in reference implementation: "Negative values are only allowed in dayofmonth expressions"
    raise SchyntaxParseException("%s cannot be %d. Value must be between %d and %d." % (expression_type, value, min, max))


def _validate_date(value):
    # FIXME - add year support
    
    if value.month < 1 or value.month > 12:
        raise SchyntaxParseException("Month %d is not a valid month. Must be between 1 and 12." % value.month)
    
    # (also year support here...)
    year = 2000  # default to a leap year, if no year is specified
    days_in_month = get_days_in_month(year, value.month)
    
    if value.day < 1 or value.day > days_in_month:
        raise SchyntaxParseException("%d is not a valid day for the month specified. Must be between 1 and %d" % (value.day, days_in_month))


def _compile_integer_range(expression_type, argument, min, max, allow_negative=False):
    '''
    Return an [integer] Range instance for the argument
    '''
    if argument.mod is not None:
        has_interval_specified = True
        effective_interval = argument.mod
    else:
        has_interval_specified = False
        effective_interval = 1
    
    if argument.is_wildcard:
        return Range(min, max, False, effective_interval)
    else:
        # if interval specified but no range, then use the max. This part is in 
        # the C# ref language and the test suite, but not clear in spec.
        # Also convert a non-range into a range (eg 5 becomes 5..5)
        if argument.end is not None:
            effective_end = argument.end
        elif has_interval_specified:
            effective_end = max
        else:
            effective_end = argument.start
        
        # Validating here, though the reference implementations do validation separately.
        # Note the reference C# still checks for disallowed negative values in the parser phase though.
        # Note the reference C# implementation currently raises SchyntaxParseException, why not InvalidScheduleException I wonder?
        # And note the reference impl uses different strings
        _validate_integer(expression_type, argument.start, min, max, allow_negative)
        _validate_integer(expression_type, effective_end, min, max, allow_negative)
        
        return Range(argument.start, effective_end, argument.is_half_open, effective_interval)


def _compile_date_range(argument):
    '''
    Return a [date] Range instance for the argument
    '''
    if argument.mod is not None:
        has_interval_specified = True
        effective_interval = argument.mod
    else:
        has_interval_specified = False
        effective_interval = 1
    
    if argument.is_wildcard:
        return Range(DateValue(1, 1), DateValue(12, 31), interval=effective_interval)
    
    # if interval but no range, use max.
    # also convert non-range into range.
    if argument.end is not None:
        effective_end = argument.end
    elif has_interval_specified:
        effective_end = DateValue(12, 31)
    else:
        effective_end = argument.start
    
    _validate_date(argument.start)
    _validate_date(effective_end)
    
    return Range(argument.start, effective_end, argument.is_half_open, effective_interval)


# this is quite different from the similarly named function in ref implementation.
# that one performs more validation based on the expression type
def _parse_integer_value(string):
    try:
        return int(string)
    except ValueError:
        try:
            return _day_of_week_literals[string.lower()]
        except KeyError:
            raise SchyntaxParseException("unknown integer or day-of-week literal: %r" % string)


def _parse_date_value(string):
    # FIXME - add support for years
    try:
        month, day = [int(x) for x in string.split('/')]
    except ValueError:
        raise SchyntaxParseException("unknown date literal: %r" % string)
    
    return DateValue(month, day)


def _parse_argument(string, is_date):
    '''
    returns 2-tuple: (Argument, remainder_of_string)
    '''
    match = _argument_regex.match(string)
    if not match:
        raise SchyntaxParseException("parse error near %r" % string)
    exclamation, asterisk, first_value, range_operator, second_value, mod_value = match.groups()
    
    
    # mod_value always has to be an integer if provided, consider that part of the basic syntax parsing
    if mod_value is not None:
        mod_value = int(mod_value)          # regex should ensure this works
        if mod_value < 1:
            raise SchyntaxParseException("interval must be greater than 0")

    argument = Argument()
    argument.is_exclude = exclamation == '!'
    argument.mod = mod_value
    
    parse_value = _parse_date_value if is_date else _parse_integer_value

    if asterisk:
        argument.is_wildcard = True
        
    elif second_value is not None:
        argument.start = parse_value(first_value)
        argument.end = parse_value(second_value)
        if range_operator == '..<':
            argument.is_half_open = True
        
    else:
        argument.start = parse_value(first_value)
        argument.end = None
    
    return argument, string[match.end():]
    

def _parse_group(string):
    # Check for empty string.
    string = string.strip()
    if not string:
        return None
    
    group = Group()
    
    while string:
        match = _expression_regex.match(string)
        if not match:
            raise SchyntaxParseException("parse error near %r" % string)
        func_name, args_string = match.groups()
        string = string[len(match.group()):]
        
        # look up and unify expression type name, and ignore case
        expression_type = _expression_types.get(func_name.lower())
        if not expression_type:
            raise SchyntaxParseException("expression type %r not supported" % func_name)
        
        # Check for zero args. The regex above already stripped space for us.
        if not args_string:
            raise SchyntaxParseException("expression requires arguments")
        
        while args_string:
            # This also eats a comma, which may allow bare comma at end. not sure if that is legal
            argument, args_string = _parse_argument(args_string, (expression_type == 'dates'))

            if expression_type == 'dates':
                if argument.is_exclude:
                    group.dates_excluded.append(_compile_date_range(argument))
                else:
                    group.dates.append(_compile_date_range(argument))
                
            elif expression_type == 'dow':
                if argument.is_exclude:
                    group.days_of_week_excluded.append(_compile_integer_range(expression_type, argument, 1, 7))
                else:
                    group.days_of_week.append(_compile_integer_range(expression_type, argument, 1, 7))
            
            elif expression_type == 'dom':
                if argument.is_exclude:
                    group.days_of_month_excluded.append(_compile_integer_range(expression_type, argument, 1, 31, True))
                else:
                    group.days_of_month.append(_compile_integer_range(expression_type, argument, 1, 31, True))
            
            elif expression_type == 'hours':
                if argument.is_exclude:
                    group.hours_excluded.append(_compile_integer_range(expression_type, argument, 0, 23))
                else:
                    group.hours.append(_compile_integer_range(expression_type, argument, 0, 23))
                    
            elif expression_type == 'minutes':
                if argument.is_exclude:
                    group.minutes_excluded.append(_compile_integer_range(expression_type, argument, 0, 59))
                else:
                    group.minutes.append(_compile_integer_range(expression_type, argument, 0, 59))
                    
            elif expression_type == 'seconds':
                if argument.is_exclude:
                    group.seconds_excluded.append(_compile_integer_range(expression_type, argument, 0, 59))
                else:
                    group.seconds.append(_compile_integer_range(expression_type, argument, 0, 59))
                
            else:
                # should not occur
                raise Exception("internal error, unknown expression type")
    
    # "setup implied rules"
    if group.seconds or group.seconds_excluded:
        # "don't need to setup any defaults if seconds are defined"
        pass
        
    elif group.minutes or group.minutes_excluded:
        group.seconds.append(Range(0, 0))
        
    elif group.hours or group.hours_excluded:
        group.seconds.append(Range(0, 0))
        group.minutes.append(Range(0, 0))
        
    else:  # "only a date level expression was set"
        group.seconds.append(Range(0, 0))
        group.minutes.append(Range(0, 0))
        group.hours.append(Range(0, 0))
    
    return group


def parse(string):
    groups = []
    string = string.strip()
    
    while string:
        
        if string.startswith('{'):
            # a group
            try:
                closing_index = string.index('}')
            except ValueError:
                raise SchyntaxParseException("missing '}' to terminate group")
            group_content_string = string[1:closing_index]
            string = string[closing_index + 1:]
            
            group = _parse_group(group_content_string)
            if group is not None:
                groups.append(group)
            
        else:
            # loose expressions are placed together into a group.
            
            # FIXME -  This may differ from the C# reference implementation!
            # In the C# implementation, the loose ones go into one group even if they are
            # separated by intervening groups.  This means they are treated together.
            # In this implementation, they go into their own groups. 
            # So the result is quite different.  
            # e.g.: "hour(5) {...} minute(10)"
            # is not 3 groups which would have "or" behavior, but 2 groups 
            # so the minutes/seconds are anded together.
            # In C# that matches only at 05:10 but mine matches 
            # both 05:00 and at 10 past every hour.
            
            if '{' in string:
                opening_index = string.index('{')
                group_content_string = string[:opening_index]
                string = string[opening_index:]
            else:
                group_content_string = string
                string = ""
            
            group = _parse_group(group_content_string)
            if group is not None:
                groups.append(group)
            
        # optional comma between groups
        # Note this allows a trailing comma, which the C# reference 
        # implementation appears to do too
        if string.startswith(','):
            string = string[1:]

    # TODO - ought to be in the validator, not the parser.
    if not groups:
        raise InvalidScheduleException("Schedule must contain at least one expression.")

    return groups

