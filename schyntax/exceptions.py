
class SchyntaxException(Exception):
    pass


# FIXME - should take (message, input, index) parameters for 
#         indicating where error is in input string
class SchyntaxParseException(SchyntaxException):
    pass


# FIXME - InvalidScheduleException


# FIXME - should take schedule,message params (well may want to change that for py a tad)
class ValidTimeNotFoundException(SchyntaxException):
    pass

