#!/usr/bin/env python3
"""
Test file with various Python errors and warnings for diagnostic testing.
This file contains intentional issues to trigger LSP diagnostics.
"""

# Unused import warning
import os
import sys
import json  # This import is unused

# Undefined variable error
def calculate_area(radius):
    """Calculate area of a circle with intentional error."""
    return pi * radius * radius  # ERROR: 'pi' is undefined

# Syntax error
def broken_function(
    """Missing closing parenthesis and colon"""
    x = 5
    return x + 1

# Type error - incompatible types
result = "hello" + 5  # ERROR: can't add string and int

# Undefined function call
undefined_function()  # ERROR: function not defined

# Variable used before assignment
def use_before_assign():
    """Function with variable used before assignment."""
    print(undefined_var)  # ERROR: undefined variable
    undefined_var = "assigned later"

# Indentation error
def indentation_error():
    """Function with indentation issues."""
    x = 5
        y = 10  # ERROR: unexpected indent
    return x + y

# Shadowing built-in names (warning)
list = [1, 2, 3]  # WARNING: shadows built-in name 'list'
str = "hello"     # WARNING: shadows built-in name 'str'

# Unused variable warnings
def unused_variables():
    """Function with unused variables."""
    unused_var = 42
    another_unused = "test"
    return "only this is used"

# Line too long (style warning)
very_long_line = "This is an extremely long line that exceeds the typical line length limit and should trigger a style warning from the linter" * 5

# Missing docstring (style warning)
def no_docstring():
    pass

# Complex nested structure with issues
class Calculator:
    """Calculator class with intentional issues."""
    
    def __init__(self):
        self.value = 0
    
    def add(self, x):
        # Missing type hints
        return self.value + x
    
    def divide(self, x):
        """Division with potential ZeroDivisionError."""
        return self.value / x  # WARNING: possible ZeroDivisionError

# Global variable issues
GLOBAL_VAR = "SHOULD_BE_CONSTANT"  # WARNING: should be lowercase

# Import issues
try:
    import nonexistent_module  # ERROR: module not found
except ImportError:
    pass

# Function redefinition
def duplicate_function():
    return 1

def duplicate_function():  # ERROR: function redefinition
    return 2

# Lambda with issues
bad_lambda = lambda x: x + y  # ERROR: 'y' not defined

# List comprehension issues
result = [x for x in range(10) if x > 5]  # 'x' shadows outer scope

# Dictionary issues
my_dict = {
    'key1': 'value1',
    'key1': 'value2'  # WARNING: duplicate key
}

# String formatting issues
name = "World"
message = f"Hello, {name} {undefined_var}"  # ERROR: undefined variable in f-string

# Comparison issues
if 5 == "5":  # WARNING: comparing int with string
    print("This might not do what you expect")

# Method issues
class TestClass:
    def method1(self):
        return self.nonexistent_attribute  # ERROR: attribute not defined
    
    @staticmethod
    def static_method(self):  # WARNING: static method with self parameter
        return 42

# File I/O issues
def read_file():
    f = open('nonexistent.txt')  # WARNING: file not found, no error handling
    return f.read()

# Mutable default argument
def bad_default(value=[]):  # WARNING: mutable default argument
    value.append(1)
    return value

# Main execution with issues
if __name__ == "__main__":
    calc = Calculator()
    print(calculate_area(5))  # Will fail due to undefined 'pi'
    print(result)  # Will show type error result
    broken_function()  # Will fail due to syntax error