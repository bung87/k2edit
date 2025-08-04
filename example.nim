# Sample Nim code for testing syntax highlighting
# Based on tree-sitter-nim grammar from https://github.com/alaviss/tree-sitter-nim

proc hello(name: string): string =
  result = "Hello, " & name & "!"

proc fibonacci(n: int): int =
  if n <= 1:
    return n
  else:
    return fibonacci(n - 1) + fibonacci(n - 2)

type
  Person = object
    name: string
    age: int

proc createPerson(name: string, age: int): Person =
  Person(name: name, age: age)

const
  MAX_AGE = 150
  DEFAULT_NAME = "Unknown"

var
  counter = 0
  people: seq[Person]

echo hello("World")
echo "Fibonacci of 10: ", fibonacci(10)

let person = createPerson("Alice", 30)
people.add(person)

for p in people:
  echo p.name, " is ", p.age, " years old"