from schyntax.internals import token
from schyntax.internals.lexer import tokenize
from schyntax.internals.dateutil import get_days_in_month
from schyntax.exceptions import SchyntaxParseException, InvalidScheduleException


EXPRESSION_TYPE_DATES = 'dates'
EXPRESSION_TYPE_DAYOFMONTH = 'dom'
EXPRESSION_TYPE_DAYOFWEEK = 'dow'
EXPRESSION_TYPE_HOURS = 'hours'
EXPRESSION_TYPE_MINUTES = 'minutes'
EXPRESSION_TYPE_SECONDS = 'seconds'


# Map of allowed expression "function" names to the internal string used by the parser
_expression_aliases = {
    's': EXPRESSION_TYPE_SECONDS,
    'sec': EXPRESSION_TYPE_SECONDS,
    'second': EXPRESSION_TYPE_SECONDS,
    'seconds': EXPRESSION_TYPE_SECONDS,
    'secondofminute': EXPRESSION_TYPE_SECONDS,
    'secondsofminute': EXPRESSION_TYPE_SECONDS,
    
    'm': EXPRESSION_TYPE_MINUTES,
    'min': EXPRESSION_TYPE_MINUTES,
    'minute': EXPRESSION_TYPE_MINUTES,
    'minutes': EXPRESSION_TYPE_MINUTES,
    'minuteofhour': EXPRESSION_TYPE_MINUTES,
    'minutesofhour': EXPRESSION_TYPE_MINUTES,
    
    'h': EXPRESSION_TYPE_HOURS,
    'hour': EXPRESSION_TYPE_HOURS,
    'hours': EXPRESSION_TYPE_HOURS,
    'hourofday': EXPRESSION_TYPE_HOURS,
    'hoursofday': EXPRESSION_TYPE_HOURS,
    
    'day': EXPRESSION_TYPE_DAYOFWEEK,
    'days': EXPRESSION_TYPE_DAYOFWEEK,
    'dow': EXPRESSION_TYPE_DAYOFWEEK,
    'dayofweek': EXPRESSION_TYPE_DAYOFWEEK,
    'daysofweek': EXPRESSION_TYPE_DAYOFWEEK,
    
    'dom': EXPRESSION_TYPE_DAYOFMONTH,
    'dayofmonth': EXPRESSION_TYPE_DAYOFMONTH,
    'daysofmonth': EXPRESSION_TYPE_DAYOFMONTH,
    
    'date': EXPRESSION_TYPE_DATES,
    'dates': EXPRESSION_TYPE_DATES,
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


# Internal, used during parsing
class Argument(object):
    is_exclusion = False
    
    is_wildcard = False
    
    start = None
    end = None              # None if not specified
    is_half_open = False
    
    interval = None         # None if not specified


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
    year = None         # None if not specified
    month = None
    day = None
    
    def __init__(self, year, month, day):
        self.year = year
        self.month = month
        self.day = day

    def __eq__(self, other):
        return self.year == other.year and self.month == other.month and self.day == other.day
        
    def __lt__(self, other):
        # not valid to compare full and partial dates
        if (self.year is None) != (other.year is None):
            raise Exception("cannot compare full and partial dates")
        
        return (self.year, self.month, self.day) < (other.year, other.month, other.day)


class Parser(object):
    def __init__(self, input):
        self._input = input
        self._tokenizer = tokenize(input)
        self._next = None
    
    ####################
    # Basic parse utils
    ####################
    
    def _is_next(self, token_type):
        return self._next.type == token_type
    
    def _advance(self):
        '''
        Advance to next input token, and return the old one.
        '''
        prev_token = self._next
        try:
            self._next = next(self._tokenizer)
        except StopIteration:
            self._next = token.Token(token.TYPE_END_OF_INPUT, "", len(self._input))
        return prev_token
    
    def _expect(self, token_type):
        '''
        If current token matches the given type, return the token and advance.
        Otherwise, raise a SchyntaxParseException.
        '''
        if self._is_next(token_type):
            return self._advance()
        else:
            self._raise_wrong_token(token_type)
    
    def _optional(self, token_type):
        '''
        If current token matches the given type, return the token and advance.
        Otherwise, return None.
        '''
        if self._is_next(token_type):
            return self._advance()
        else:
            return None
    
    def _raise_wrong_token(self, *types):
        index = self._next.index
        got_name = token.get_token_type_name(self._next.type)
        expected_names = [token.get_token_type_name(token_type) for token_type in types]
        
        expected_phrase = ", ".join(expected_names)
        if len(expected_names) > 1:
            expected_phrase = "one of " + expected_phrase
        
        # TODO - I don't think the reference C# does this, but should make this better, especially at END_OF_INPUT
        raise SchyntaxParseException("Unexpected token type %s at index %d. Was expecting %s" % (got_name, index, expected_phrase), self._input, index)

    def _get_current_index(self):
        return self._next.index

    ####################
    # Main parse logic
    ####################
    
    def parse(self):
        # Prime the first look-ahead token.
        self._advance()
        
        return self._parse_program()
        
    def _parse_program(self):
        groups = []
        loose_expression_group = None
        
        while not self._is_next(token.TYPE_END_OF_INPUT):
            if self._is_next(token.TYPE_OPEN_CURLY):
                groups.append(self._parse_group())
            
            elif self._is_next(token.TYPE_WORD):
                if loose_expression_group is None:
                    loose_expression_group = Group()
                    groups.append(loose_expression_group)
                self._parse_expression(loose_expression_group)
                
            else:
                self._raise_wrong_token(token.TYPE_OPEN_CURLY, token.TYPE_WORD)
            
            self._optional(token.TYPE_COMMA)
        
        # validate that at least one group or expression is found
        if not groups:
            raise InvalidScheduleException("Schedule must contain at least one expression.")
        
        # apply higher-resolution defaults to all groups, even the loose group
        for group in groups:
            self._add_defaults(group)
        
        return groups

    def _parse_group(self):
        group = Group()
        self._expect(token.TYPE_OPEN_CURLY)
        
        # validate that at least one expression is found inside the group
        if self._is_next(token.TYPE_CLOSE_CURLY):
            raise InvalidScheduleException("Schedule must contain at least one expression.")
        
        while not self._is_next(token.TYPE_CLOSE_CURLY):
            self._parse_expression(group)
            self._optional(token.TYPE_COMMA)
        
        self._expect(token.TYPE_CLOSE_CURLY)
        return group
    
    def _parse_expression(self, group):
        expression_name_token = self._expect(token.TYPE_WORD)
        
        # lookup expression type
        expression_type = _expression_aliases.get(expression_name_token.string.lower())
        if not expression_type:
            raise SchyntaxParseException("expression type %r not supported" % expression_name_token.string, self._input, expression_name_token.index)
        
        self._expect(token.TYPE_OPEN_PAREN)
        
        # do-while style loop to ensure at least one argument is found
        while True:
            arg = self._parse_argument(expression_type)
            self._add_argument(group, expression_type, arg)
            
            self._optional(token.TYPE_COMMA)
            
            if self._is_next(token.TYPE_CLOSE_PAREN):
                break
        
        self._expect(token.TYPE_CLOSE_PAREN)
    
    def _parse_argument(self, expression_type):
        first_token_index = self._get_current_index()
        
        arg = Argument()
        
        if self._optional(token.TYPE_NOT):
            arg.is_exclusion = True
        
        if self._optional(token.TYPE_WILDCARD):
            arg.is_wildcard = True
        else:
            self._parse_range(expression_type, arg)
        
        if self._optional(token.TYPE_INTERVAL):
            tok = self._expect(token.TYPE_INTEGER)
            arg.interval = int(tok.string)
            if arg.interval <= 0:
                raise SchyntaxParseException('"%d" is not a valid interval' % arg.interval, self._input, tok.index)
        
        if arg.is_wildcard and arg.is_exclusion and arg.interval is None:
            raise SchyntaxParseException("Wildcards can't be excluded with the ! operator, except when part of an interval (using %)", self._input, first_token_index)
        
        return arg
    
    def _parse_range(self, expression_type, arg):
        first_token_index = self._get_current_index()
        
        arg.start = self._parse_range_value(expression_type)
        
        is_range = False
        if self._optional(token.TYPE_RANGE_INCLUSIVE):
            is_range = True
        elif self._optional(token.TYPE_RANGE_HALF_OPEN):
            is_range = True
            arg.is_half_open = True
        
        if is_range:
            arg.end = self._parse_range_value(expression_type)
        
        if arg.is_half_open and arg.start == arg.end:
            raise SchyntaxParseException("Start and end values of a half-open range cannot be equal.", self._input, first_token_index)
        
        if expression_type == EXPRESSION_TYPE_DATES and arg.end is not None:
            # special validation to make the date range is sane
            if arg.start.year is not None or arg.end.year is not None:
                if arg.start.year is None or arg.end.year is None:
                    raise SchyntaxParseException("Cannot mix full and partial dates in a date range.", self._input, first_token_index)
                
                if arg.start > arg.end:
                    raise SchyntaxParseException("End date of range is before the start date.", self._input, first_token_index)
        
    def _parse_range_value(self, expression_type):
        if expression_type == EXPRESSION_TYPE_DATES:
            return self._parse_date()
        
        elif expression_type == EXPRESSION_TYPE_DAYOFWEEK and self._is_next(token.TYPE_WORD):
            return self._parse_day_of_week()
        
        elif self._is_next(token.TYPE_INTEGER):
            return self._parse_integer_value(expression_type)
        
        else:
            # bad token. use expression type to compose error with what is expected
            if expression_type == EXPRESSION_TYPE_DAYOFWEEK:
                self._raise_wrong_token(token.TYPE_INTEGER, token.TYPE_WORD)
            else:
                self._raise_wrong_token(token.TYPE_INTEGER)

    def _parse_integer_value(self, expression_type):
        
        if expression_type == EXPRESSION_TYPE_DAYOFWEEK:
            return self._parse_valid_integer(expression_type, 1, 7)
        
        elif expression_type == EXPRESSION_TYPE_DAYOFMONTH:
            return self._parse_valid_integer(expression_type, 1, 31, True)
        
        elif expression_type == EXPRESSION_TYPE_HOURS:
            return self._parse_valid_integer(expression_type, 0, 23)
        
        elif expression_type == EXPRESSION_TYPE_MINUTES:
            return self._parse_valid_integer(expression_type, 0, 59)
        
        elif expression_type == EXPRESSION_TYPE_SECONDS:
            return self._parse_valid_integer(expression_type, 0, 59)
        
        else:
            # internal error, should not reach here
            raise Exception("invalid state")
    
    def _parse_valid_integer(self, expression_type, min, max, allow_negative=False):
        tok = self._expect(token.TYPE_INTEGER)
        value = int(tok.string)
        
        self._validate_integer(value, min, max, allow_negative, tok.index)
        return value
        
    def _parse_date(self):
        first_token_index = self._get_current_index()
        
        parts = []
        parts.append(int(self._expect(token.TYPE_INTEGER).string))
        self._expect(token.TYPE_FORWARD_SLASH)
        parts.append(int(self._expect(token.TYPE_INTEGER).string))
        if self._optional(token.TYPE_FORWARD_SLASH):
            parts.append(int(self._expect(token.TYPE_INTEGER).string))
        
        if len(parts) == 3:
            date = DateValue(*parts)
        else:
            date = DateValue(None, *parts)
        
        self._validate_date(date, first_token_index)
        return date
    
    def _parse_day_of_week(self):
        tok = self._expect(token.TYPE_WORD)
        
        try:
            return _day_of_week_literals[tok.string.lower()]
        except KeyError:
            raise SchyntaxParseException("unknown integer or day-of-week literal: %r" % tok.string, self._input, tok.index)

    ####################
    # Value validation
    ####################
    
    def _validate_integer(self, value, min, max, allow_negative, index):
        if min <= value <= max:
            return
        if value < 0 and allow_negative and min <= -value <= max:
            return
        
        #if allow_negative: perhaps to adjust the exception message?
        # note this appears in reference implementation: "Negative values are only allowed in dayofmonth expressions"
        #
        # FIXME - better message using expression type
        raise SchyntaxParseException("Value cannot be %d. Value must be between %d and %d." % (value, min, max), self._input, index)

    def _validate_date(self, value, index):
        
        if value.year is not None:
            if value.year < 1900 or value.year > 2200:
                raise SchyntaxParseException("Year %d is not a valid year. Must be between 1900 and 2200." % value.year, self._input, index)
        
        if value.month < 1 or value.month > 12:
            raise SchyntaxParseException("Month %d is not a valid month. Must be between 1 and 12." % value.month, self._input, index)
        
        year = value.year
        if year is None:
            year = 2000  # default to a leap year, if no year is specified
        days_in_month = get_days_in_month(year, value.month)
        
        if value.day < 1 or value.day > days_in_month:
            raise SchyntaxParseException("%d is not a valid day for the month specified. Must be between 1 and %d" % (value.day, days_in_month), self._input, index)


    ####################
    # FIXME - name section
    ####################
    
    def _add_defaults(self, group):
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
    
    def _add_argument(self, group, expression_type, argument):
        
        if expression_type == EXPRESSION_TYPE_DATES:
            if argument.is_exclusion:
                group.dates_excluded.append(self._compile_date_range(argument))
            else:
                group.dates.append(self._compile_date_range(argument))
            
        elif expression_type == EXPRESSION_TYPE_DAYOFWEEK:
            if argument.is_exclusion:
                group.days_of_week_excluded.append(self._compile_integer_range(argument, 1, 7))
            else:
                group.days_of_week.append(self._compile_integer_range(argument, 1, 7))
        
        elif expression_type == EXPRESSION_TYPE_DAYOFMONTH:
            if argument.is_exclusion:
                group.days_of_month_excluded.append(self._compile_integer_range(argument, 1, 31))
            else:
                group.days_of_month.append(self._compile_integer_range(argument, 1, 31))
        
        elif expression_type == EXPRESSION_TYPE_HOURS:
            if argument.is_exclusion:
                group.hours_excluded.append(self._compile_integer_range(argument, 0, 23))
            else:
                group.hours.append(self._compile_integer_range(argument, 0, 23))
        
        elif expression_type == EXPRESSION_TYPE_MINUTES:
            if argument.is_exclusion:
                group.minutes_excluded.append(self._compile_integer_range(argument, 0, 59))
            else:
                group.minutes.append(self._compile_integer_range(argument, 0, 59))
        
        elif expression_type == EXPRESSION_TYPE_SECONDS:
            if argument.is_exclusion:
                group.seconds_excluded.append(self._compile_integer_range(argument, 0, 59))
            else:
                group.seconds.append(self._compile_integer_range(argument, 0, 59))
        
        else:
            # internal error, should not reach here
            raise Exception("invalid state")

    def _compile_integer_range(self, argument, min, max):
        '''
        Return an [integer] Range instance for the argument
        '''
        if argument.interval is not None:
            has_interval_specified = True
            effective_interval = argument.interval
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
            
            return Range(argument.start, effective_end, argument.is_half_open, effective_interval)
    
    def _compile_date_range(self, argument):
        '''
        Return a [date] Range instance for the argument
        '''
        if argument.interval is not None:
            has_interval_specified = True
            effective_interval = argument.interval
        else:
            has_interval_specified = False
            effective_interval = 1
        
        if argument.is_wildcard:
            return Range(DateValue(None, 1, 1), DateValue(None, 12, 31), interval=effective_interval)
        
        # if interval but no range, use max.
        # also convert non-range into range.
        if argument.end is not None:
            effective_end = argument.end
        elif has_interval_specified:
            effective_end = DateValue(None, 12, 31)
        else:
            effective_end = argument.start
        
        return Range(argument.start, effective_end, argument.is_half_open, effective_interval)


def parse(string):
    return Parser(string).parse()

