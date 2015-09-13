import re


# meta
# (skipping the NONE in the C#)
TYPE_END_OF_INPUT = 1

# operators
TYPE_RANGE_INCLUSIVE = 2
TYPE_RANGE_HALF_OPEN = 3
TYPE_INTERVAL = 4
TYPE_NOT = 5
TYPE_OPEN_PAREN = 6
TYPE_CLOSE_PAREN = 7
TYPE_OPEN_CURLY = 8
TYPE_CLOSE_CURLY = 9
TYPE_FORWARD_SLASH = 10
TYPE_COMMA = 11
TYPE_WILDCARD = 12

# alpha-numeric.
# NOTE - these differ from the C# reference implementation
TYPE_INTEGER = 13
TYPE_WORD = 14


class TokenType(object):
    type = None         # TYPE_XXX enum
    pattern = None      # string or compiled RegExp.  None for special end of input psuedo type.
    name = None         # human-readable string for error messages
    
    def __init__(self, type, pattern, name=None):
        # for plain string types, just use the pattern itself, such as "{"
        if not name:
            assert isinstance(pattern, str), "name required for regex-based token types"
            name = "'%s'" % pattern
        
        self.type = type
        self.pattern = pattern
        self.name = name


token_types = [
    # meta
    TokenType(TYPE_END_OF_INPUT, None, "end-of-input"),
    
    # operators
    TokenType(TYPE_RANGE_HALF_OPEN, "..<"),        # must be before range inclusive to match
    TokenType(TYPE_RANGE_INCLUSIVE, ".."),
    TokenType(TYPE_INTERVAL, "%"),
    TokenType(TYPE_NOT, "!"),
    TokenType(TYPE_OPEN_PAREN, "("),
    TokenType(TYPE_CLOSE_PAREN, ")"),
    TokenType(TYPE_OPEN_CURLY, "{"),
    TokenType(TYPE_CLOSE_CURLY, "}"),
    TokenType(TYPE_FORWARD_SLASH, "/"),
    TokenType(TYPE_COMMA, ","),
    TokenType(TYPE_WILDCARD, "*"),
    
    # alpha-numeric
    TokenType(TYPE_WORD, re.compile(r'[a-zA-Z]+\b'), "word"),
    TokenType(TYPE_INTEGER, re.compile(r'-?[0-9]+\b'), "integer"),
]


def get_token_type_name(type):
    for token_type in token_types:
        if token_type.type == type:
            return token_type.name
    
    # should not occur
    raise Exception("unknown token type")
        

class Token(object):
    type = None         # TYPE_XXX enum
    string = None       # raw token string from input
    index = None
    
    def __init__(self, type, string, index):
        self.type = type
        self.string = string
        self.index = index

