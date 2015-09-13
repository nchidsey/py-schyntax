# py-schyntax

A simple Python library for parsing [Schyntax](https://github.com/schyntax/schyntax) schedule strings, and finding the next scheduled event time.  

This is an unofficial Python implementation of Schyntax.  See the C# [reference implementation](https://github.com/schyntax/cs-schyntax).  Tested with Python 2.7 and 3.4.

## Usage

Every 5 minutes:

```python
import schyntax

schedule = schyntax.Schedule("minutes(* % 5)")
print(schedule.next())
```

Find the next weekday (Monday through Friday) at 16:00 UTC:

```python
schedule = schyntax.Schedule("hours(16), days(mon..fri)")
print(schedule.next())
```


### `Schedule.next([after])`

Accepts an optional `after` argument in the form of a `datetime`. If no argument is provided, the current time is used.

Returns a `datetime` object representing the next timestamp which matches the scheduling criteria. The date will always be greater than, never equal to, `after`. If no timestamp could be found which matches the scheduling criteria, a `ValidTimeNotFoundException` is raised, which generally indicates conflicting scheduling criteria (explicitly including and excluding the same day or time).

### `Schedule.previous([at_or_before])`

Same as `previous()` except that its return value will be less than or equal to the current time or optional `at_or_before` argument. This means that if you want to find the last n-previous events, you should subtract at least a millisecond from the result before passing it back to the function.


## Syntax

For complete documentation on the Schyntax domain-specific language, see the [Schyntax project](https://github.com/schyntax/schyntax).
