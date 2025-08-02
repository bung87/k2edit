# Example Nim Program - A Simple Task Manager

import strformat
import strutils
import times
import os
import tables

# Define a Task type
type
  Priority = enum
    Low = 1
    Medium = 2
    High = 3
  
  Task = object
    id: int
    title: string
    description: string
    priority: Priority
    created: DateTime
    completed: bool

# Global task storage
var tasks: seq[Task] = @[]
var nextId = 1

# Procedure to create a new task
proc createTask(title, description: string, priority: Priority = Medium): Task =
  result = Task(
    id: nextId,
    title: title,
    description: description,
    priority: priority,
    created: now(),
    completed: false
  )
  inc(nextId)

# Procedure to display a task
proc displayTask(task: Task) =
  let status = if task.completed: "✓" else: "○"
  let priorityStr = case task.priority
    of Low: "Low"
    of Medium: "Medium"
    of High: "High"
  
  echo fmt"{status} [{task.id}] {task.title}"
  echo fmt"  Priority: {priorityStr}"
  echo fmt"  Created: {task.created.format("yyyy-MM-dd HH:mm")}"
  echo fmt"  Description: {task.description}"
  echo ""

# Procedure to list all tasks
proc listTasks() =
  if tasks.len == 0:
    echo "No tasks found."
    return
  
  echo fmt"Found {tasks.len} task(s):"
  echo ""
  for task in tasks:
    displayTask(task)

# Procedure to complete a task
proc completeTask(id: int): bool =
  for i in 0 ..< tasks.len:
    if tasks[i].id == id:
      tasks[i].completed = true
      return true
  return false

# Procedure to delete a task
proc deleteTask(id: int): bool =
  for i in 0 ..< tasks.len:
    if tasks[i].id == id:
      tasks.delete(i)
      return true
  return false

# Procedure to save tasks to file
proc saveTasks(filename: string) =
  try:
    var file = open(filename, fmWrite)
    defer: file.close()
    
    for task in tasks:
      let line = fmt"{task.id}|{task.title}|{task.description}|{ord(task.priority)}|{task.completed}|{task.created.format("yyyy-MM-dd HH:mm")}"
      file.writeLine(line)
    
    echo fmt"Tasks saved to {filename}"
  except IOError:
    echo fmt"Error: Could not save to {filename}"

# Procedure to load tasks from file
proc loadTasks(filename: string) =
  if not fileExists(filename):
    return
  
  try:
    var file = open(filename, fmRead)
    defer: file.close()
    
    tasks = @[]
    nextId = 1
    
    for line in file.lines:
      let parts = line.split('|')
      if parts.len == 6:
        var task = Task(
          id: parseInt(parts[0]),
          title: parts[1],
          description: parts[2],
          priority: Priority(parseInt(parts[3])),
          completed: parseBool(parts[4]),
          created: parse(parts[5], "yyyy-MM-dd HH:mm")
        )
        tasks.add(task)
        nextId = max(nextId, task.id + 1)
    
    echo fmt"Loaded {tasks.len} task(s) from {filename}"
  except IOError:
    echo fmt"Error: Could not load from {filename}"
  except ValueError:
    echo "Error: Invalid file format"

# Main menu procedure
proc showMenu() =
  echo ""
  echo "=== Nim Task Manager ==="
  echo "1. Add task"
  echo "2. List tasks"
  echo "3. Complete task"
  echo "4. Delete task"
  echo "5. Save tasks"
  echo "6. Load tasks"
  echo "7. Exit"
  echo ""

# Main program
proc main() =
  let filename = "tasks.txt"
  loadTasks(filename)
  
  while true:
    showMenu()
    
    stdout.write("Enter your choice (1-7): ")
    let choice = stdin.readLine().strip()
    
    case choice
    of "1":
      stdout.write("Enter task title: ")
      let title = stdin.readLine().strip()
      
      stdout.write("Enter task description: ")
      let description = stdin.readLine().strip()
      
      stdout.write("Enter priority (1=Low, 2=Medium, 3=High): ")
      let priorityInput = stdin.readLine().strip()
      
      let priority = case priorityInput
        of "1": Low
        of "3": High
        else: Medium
      
      let task = createTask(title, description, priority)
      tasks.add(task)
      echo "Task added successfully!"
      
    of "2":
      listTasks()
      
    of "3":
      stdout.write("Enter task ID to complete: ")
      let idStr = stdin.readLine().strip()
      
      try:
        let id = parseInt(idStr)
        if completeTask(id):
          echo "Task completed!"
        else:
          echo "Task not found."
      except ValueError:
        echo "Invalid ID."
        
    of "4":
      stdout.write("Enter task ID to delete: ")
      let idStr = stdin.readLine().strip()
      
      try:
        let id = parseInt(idStr)
        if deleteTask(id):
          echo "Task deleted!"
        else:
          echo "Task not found."
      except ValueError:
        echo "Invalid ID."
        
    of "5":
      saveTasks(filename)
      
    of "6":
      loadTasks(filename)
      
    of "7":
      saveTasks(filename)
      echo "Goodbye!"
      break
      
    else:
      echo "Invalid choice. Please enter 1-7."

# Run the program
when isMainModule:
  main()