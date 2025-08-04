# File Explorer Context Addition Feature

## Overview
This feature adds the ability to add files to AI assistant context directly from the file explorer using keyboard shortcuts.

## How to Use

### Adding Files to AI Context
1. **Navigate the File Explorer**: Use arrow keys to move through the file tree
2. **Select a File**: Highlight the file you want to add to context
3. **Add to Context**: Press the **'a'** key to add the selected file to AI context
4. **Confirmation**: You'll see a notification confirming the file was added

### Visual Indicators
- 📄 **Document emoji**: Files that can be added to context are marked with 📄
- **Keyboard hints**: When you highlight a file, you'll see a hint showing "Press 'a' to add to AI context"

### Example Usage
```
📁 src/
  📁 backend/
    📄 main.py
    📄 config.py
  📁 frontend/
    📄 app.js
```

To add `main.py` to AI context:
1. Navigate to `main.py` using arrow keys
2. Press **'a'** key
3. See confirmation: "Added main.py to AI context"

## Technical Implementation

### Components Modified
- **file_explorer.py**: Added AddToContext message and keyboard handling
- **main.py**: Added message handler and integration with agent system
- **agent/context_manager.py**: Added add_context_file method
- **agent/integration.py**: Added integration layer for context addition

### Keyboard Shortcuts
- **a**: Add selected file to AI context
- **Enter**: Open selected file in editor
- **Arrow keys**: Navigate file tree

### Error Handling
- If a file cannot be read, an error message will be displayed
- If the agent system is not initialized, an appropriate message will be shown
- Directories cannot be added to context (only files)

## Testing

### Manual Testing Steps
1. Start the application: `python3 main.py`
2. Navigate to any Python file in the explorer
3. Press **'a'** key while file is selected
4. Check output panel for confirmation message
5. Verify the file appears in AI context for subsequent queries

### Expected Behavior
- File explorer shows document emoji (📄) next to files
- Pressing 'a' on a file adds it to AI context
- Confirmation message appears in output panel
- File content is available for AI queries