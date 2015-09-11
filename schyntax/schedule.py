import datetime

from schyntax.parser import parse
from schyntax.exceptions import ValidTimeNotFoundException
from schyntax.dateutil import get_days_in_month, get_days_in_previous_month


__all__ = ['Schedule']


# (tweak the parameter footprint... this is gross)
# This is not very pleasant, but it lets the loops for hour, minute, second
# work more like the original C# code, which has a for loop construct
# that python just doesn't support.
#
# Yields tuples in this pattern:
#   (start, initial_extras ...)
#   (start + 1, further_extras ...)
#   (start + 2, further_extras ...)
#   ...
def _loop_helper(start, count, inc, initial_extras, further_extras):
    if count <= 0:
        return
    
    primary = start
    
    # first yield start and the values supplied in initial_extras.
    yield (primary,) + initial_extras
    
    # for the rest, increment primary and yield it with the 
    # other values supplied in further_extras.
    for i in range(count - 1):
        primary += inc
        yield (primary,) + further_extras


class Schedule(object):
    def __init__(self, string):
        self.original_text = string
        # FIXME - validate here or inside parser?
        self._groups = parse(string)
    
    def next(self, after=None):
        if after is None:
            after = datetime.datetime.utcnow()
        return self._get_event(after, True)

    def previous(self, at_or_before=None):
        if at_or_before is None:
            at_or_before = datetime.datetime.utcnow()
        return self._get_event(at_or_before, False)
    
    def _get_event(self, ref, is_after):
        # FIXME - ensure or convert given time to UTC?
        result = None
        for group in self._groups:
            e = self._try_get_group_event(group, ref, is_after)
            if e is not None:
                if result is None or (is_after and e < result) or (not is_after and e > result):
                    result = e
        if result is None:
            raise ValidTimeNotFoundException()
        return result
    
    def _try_get_group_event(self, group, ref, is_after):
        inc = 1 if is_after else -1
        
        init_hour = 0 if is_after else 23
        init_minute = 0 if is_after else 59
        init_second = 0 if is_after else 59
        
        # "todo: make the length of the search configurable"
        for d in range(367):
            if d == 0:
                # "'after' events must be in the future"
                date = ref
                if is_after:
                    date = date + datetime.timedelta(seconds=1)
                
                hour = date.hour
                minute = date.minute
                second = date.second
            else:
                date = ref + datetime.timedelta(days=d * inc)
                
                hour = init_hour
                minute = init_minute
                second = init_second
            
            year = date.year
            month = date.month
            day_of_week = date.isoweekday() % 7 + 1  # convert py's isoweekday to sun=1 .. sat=7
            day_of_month = date.day
            
            
            # "check if today is an applicable date"
            if group.dates and not self._in_date_rule(group.dates, year, month, day_of_month):
                continue
                
            if group.dates_excluded and self._in_date_rule(group.dates_excluded, year, month, day_of_month):
                continue
            
            
            # "check if date is an applicable day of month"
            if group.days_of_month and not self._in_dom_rule(group.days_of_month, year, month, day_of_month):
                continue
            
            if group.days_of_month_excluded and self._in_dom_rule(group.days_of_month_excluded, year, month, day_of_month):
                continue
            
            
            # "check if date is an applicable day of week"
            if group.days_of_week and not self._in_rule(7, group.days_of_week, day_of_week):
                continue
                
            if group.days_of_week_excluded and self._in_rule(7, group.days_of_week_excluded, day_of_week):
                continue
            
            
            # "if we've gotten this far, then today is an applicable day, let's keep going with hour checks"
            hour_count = 24 - hour if is_after else hour + 1
            for hour, minute, second in _loop_helper(hour, hour_count, inc, (minute, second), (init_minute, init_second)):
                
                if group.hours and not self._in_rule(24, group.hours, hour):
                    continue
                
                if group.hours_excluded and self._in_rule(24, group.hours_excluded, hour):
                    continue
                
                # "if we've gotten here, the date and hour are valid. Let's check for minutes"
                minute_count = 60 - minute if is_after else minute + 1
                for minute, second in _loop_helper(minute, minute_count, inc, (second,), (init_second,)):
                    
                    if group.minutes and not self._in_rule(60, group.minutes, minute):
                        continue
                    
                    if group.minutes_excluded and self._in_rule(60, group.minutes_excluded, minute):
                        continue
                        
                    # "check for valid seconds"
                    second_count = 60 - second if is_after else second + 1
                    for second, in _loop_helper(second, second_count, inc, (), ()):
                        
                        if group.seconds and not self._in_rule(60, group.seconds, second):
                            continue
                        
                        if group.seconds_excluded and self._in_rule(60, group.seconds_excluded, second):
                            continue
                        
                        # "we've found our event"
                        # TODO - explicitly set UTC?
                        return datetime.datetime(year, month, day_of_month, hour, minute, second)
        
        # "we didn't find an applicable date"
        return None
    
    def _in_date_rule(self, ranges, year, month, day_of_month):
        for rng in ranges:
            if self._in_date_range(rng, year, month, day_of_month):
                return True
        return False
    
    def _in_dom_rule(self, ranges, year, month, day_of_month):
        for rng in ranges:
            if self._in_dom_range(rng, year, month, day_of_month):
                return True
        return False
    
    def _in_rule(self, length_of_unit, ranges, value):
        for rng in ranges:
            if self._in_integer_range(rng, value, length_of_unit):
                return True
        return False
    
    
    def _in_date_range(self, rng, year, month, day_of_month):
        if rng.is_half_open:
            # FIXME - missing 'year' logic
            if rng.end.day == day_of_month and rng.end.month == month:  # and (rng.has_year_ornullcheck or rng.end.year == year)
                return False
        
        # FIXME - missing more year logic
        
        if rng.start > rng.end:
            # split range
            # "split ranges aren't allowed to have years (it wouldn't make any sense)"
            
            if month == rng.start.month or month == rng.end.month:
                if month == rng.start.month and day_of_month < rng.start.day:
                    return False
                
                if month == rng.end.month and day_of_month > rng.end.day:
                    return False
                
            elif not (month < rng.end.month or month > rng.start.month):
                return False
            
        else:
            # "not a split range, and no year information - just month and day to go on"
            if self._compare_month_and_day(month, day_of_month, rng.start.month, rng.start.day) < 0:
                return False
            if self._compare_month_and_day(month, day_of_month, rng.end.month, rng.end.day) > 0:
                return False
        
        # If we get here, then we're definitely somewhere within the range.
        # If there's no interval, then there's nothing else we need to check
        if rng.interval == 1:  # I just made nonspecified intervals unify to a 1
            return True
        
        # "figure out the actual date of the low date so we know whether we're on the desired interval"
        # FIXME - missing year logic
        # if rng.have_year_or_something ...
        #elif
        if rng.start > rng.end and month <= rng.end.month:
            # "start date is from the previous year"
            start_year = year - 1
        else:
            start_year = year
        
        start_day = rng.start.day
        
        # "check if start date was actually supposed to be February 29th, but isn't because of non-leap-year."
        if rng.start.month == 2 and rng.start.day == 29 and get_days_in_month(start_year, 2) != 29:
            # "bump the start day back to February 28th so that interval schemes work based on that imaginary date"
            # "but seriously, people should probably just expect weird results if they're doing something that stupid."
            start_day = 28
        
        start = datetime.date(start_year, rng.start.month, start_day)
        current = datetime.date(year, month, day_of_month)
        day_count = (current - start).days
        
        return day_count % rng.interval == 0
        
    def _compare_month_and_day(self, m1, d1, m2, d2):
        if m1 < m2 or (m1 == m2 and d1 < d2):
            return -1
        if m2 < m1 or (m2 == m1 and d2 < d1):
            return 1
        return 0
    
    def _in_dom_range(self, rng, year, month, day_of_month):
        # if either range value is negative, convert to positive by counting back from end of the month
        if rng.start < 0 or rng.end < 0:
            days_in_month = get_days_in_month(year, month)
            
            rng = rng.clone()
            
            if rng.start < 0:
                rng.start = days_in_month + rng.start + 1
            if rng.end < 0:
                rng.end = days_in_month + rng.end + 1
        
        return self._in_integer_range(rng, day_of_month, get_days_in_previous_month(year, month))

    def _in_integer_range(self, rng, value, length_of_unit):
        
        if rng.is_half_open and value == rng.end:
            return False
        
        # simple case where start <= end
        if rng.start <= value <= rng.end:
            return (value - rng.start) % rng.interval == 0
        
        # split case where start > end
        if rng.start > rng.end and (value <= rng.end or value >= rng.start):
            if value >= rng.start:
                return (value - rng.start) % rng.interval == 0
            
            return (value + length_of_unit - rng.start) % rng.interval == 0
        
        return False
