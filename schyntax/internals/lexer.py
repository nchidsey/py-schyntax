import re

from schyntax.internals.token import Token, token_types
from schyntax.exceptions import SchyntaxParseException


_RegexType = type(re.compile(""))


def tokenize(input):
    '''
    Generator that yields a series of Token instances for the input string.
    '''
    index = 0
    length = len(input)
    
    while index < length:
        # skip and ignore whitespace
        if input[index] in ' \t\r\n':
            index += 1
            continue
        
        # then check the list of token types, in order.
        for token_type in token_types:
            # skip end of input token type
            if token_type.pattern is None:
                continue
            
            if isinstance(token_type.pattern, _RegexType):
                match = token_type.pattern.match(input, index)
                if match:
                    yield Token(token_type.type, match.group(), index)
                    index = match.end()
                    break
            else:
                # plain string pattern
                if input[index : index + len(token_type.pattern)] == token_type.pattern:
                    yield Token(token_type.type, token_type.pattern, index)
                    index += len(token_type.pattern)
                    break
        else:
            # FIXME - better error message
            raise SchyntaxParseException("syntax error near: %s" % input[index:], input, index)
