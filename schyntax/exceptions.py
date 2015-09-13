
class SchyntaxException(Exception):
    pass


class SchyntaxParseException(SchyntaxException):
    def __init__(self, message, input, index):
        self.message = message
        self.input = input
        self.index = index

    def __str__(self):
        return self.message + "\n\n" + self._get_pointer_to_index()
    
    def _get_pointer_to_index(self):
        start = max(0, self.index - 20)
        length = min(len(self.input) - start, 50)
        prefix = self.input[start : start + length]
        
        return prefix + '\n' + ' ' * (self.index - start) + '^'


class InvalidScheduleException(SchyntaxException):
    pass


# FIXME - should take schedule,message params (well may want to change that for py a tad)
class ValidTimeNotFoundException(SchyntaxException):
    pass

