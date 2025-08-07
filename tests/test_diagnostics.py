# Test file with intentional syntax errors

def broken_function(
    # Missing closing parenthesis - syntax error
    print("This will cause a syntax error")
    
    # Missing colon
    if True
        print("Another error")
    
    # Undefined variable
    result = undefined_variable + 5
    
    return result

# Missing colon after class
class BrokenClass
    def __init__(self):
        pass