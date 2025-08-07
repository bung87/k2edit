"""
Pytest configuration and fixtures for K2Edit agentic system tests
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
from pathlib import Path
from aiologger import Logger


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for test projects."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_python_file(temp_project_dir):
    """Create a sample Python file for testing."""
    file_path = temp_project_dir / "sample.py"
    file_path.write_text('''
def hello_world():
    """A simple hello world function."""
    print("Hello, World!")
    return True

class Calculator:
    """A simple calculator class."""
    
    def __init__(self):
        self.total = 0
    
    def add(self, value: int) -> int:
        """Add value to total."""
        self.total += value
        return self.total
    
    def multiply(self, value: int) -> int:
        """Multiply total by value."""
        self.total *= value
        return self.total

if __name__ == "__main__":
    calc = Calculator()
    result = calc.add(5)
    print(f"Result: {result}")
''')
    return file_path


@pytest.fixture
def sample_js_file(temp_project_dir):
    """Create a sample JavaScript file for testing."""
    file_path = temp_project_dir / "sample.js"
    file_path.write_text('''
function greetUser(name) {
    return `Hello, ${name}!`;
}

class UserManager {
    constructor() {
        this.users = [];
    }
    
    addUser(name) {
        this.users.push(name);
        return this.users.length;
    }
    
    getUserCount() {
        return this.users.length;
    }
}

module.exports = { greetUser, UserManager };
''')
    return file_path


@pytest.fixture
def complex_project(temp_project_dir):
    """Create a complex project structure for testing."""
    # Create directory structure
    (temp_project_dir / "src").mkdir()
    (temp_project_dir / "src" / "utils").mkdir()
    (temp_project_dir / "tests").mkdir()
    
    # Create main.py
    (temp_project_dir / "main.py").write_text('''
from src.utils.math_utils import add, multiply
from src.calculator import Calculator

def main():
    calc = Calculator()
    result = calc.add(5)
    print(f"Calculator result: {result}")
    
if __name__ == "__main__":
    main()
''')
    
    # Create utils
    (temp_project_dir / "src" / "utils" / "math_utils.py").write_text('''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
''')
    
    # Create calculator
    (temp_project_dir / "src" / "calculator.py").write_text('''
from src.utils.math_utils import add, multiply

class Calculator:
    def __init__(self):
        self.total = 0
    
    def add(self, value: int) -> int:
        self.total = add(self.total, value)
        return self.total
    
    def multiply(self, value: int) -> int:
        self.total = multiply(self.total, value)
        return self.total
''')
    
    return temp_project_dir


@pytest.fixture
def logger():
    """Create a test logger using aiologger.Logger."""
    return Logger(name="test")