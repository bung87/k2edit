# K2Edit - Terminal Code Editor with Kimi-K2 AI Integration

A powerful terminal-based code editor built with Python and Textual, featuring full integration with the Kimi-K2 AI model for intelligent code assistance, agent mode, and tool calling capabilities.

## Features

### 🖥️ Terminal-Based Editor
- Multi-line text editing with syntax highlighting
- File operations (open, save, save as)
- Command-driven interface
- Modern terminal UI with Textual framework

### 🤖 Kimi-K2 AI Integration
- **Chat Mode**: Ask questions about your code
- **Code Explanation**: Understand complex code sections
- **Code Fixing**: Automatically detect and fix issues
- **Code Refactoring**: Improve code structure and quality
- **Test Generation**: Generate unit tests for your code
- **Documentation**: Add docstrings and comments

### 🛠️ Agent Mode
- Multi-step task execution
- Automatic tool selection and usage
- Complex goal decomposition
- File system operations

### 🔧 Tool Calling
- File read/write operations
- Code replacement and insertion
- Directory listing
- Code search and analysis
- Command execution
- Security analysis

## Installation

1. **Clone or create the project directory:**
   ```bash
   mkdir k2edit
   cd k2edit
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your Kimi API key:**
   ```bash
   cp .env.example .env
   # Edit .env and add your Kimi API key
   ```

4. **Get your Kimi API key:**
   - Visit [Moonshot AI Platform](https://platform.moonshot.ai/console/api-keys)
   - Create an account and generate an API key
   - Add it to your `.env` file:
     ```
     KIMI_API_KEY=your_actual_api_key_here
     ```

## Usage

### Starting the Editor

```bash
python main.py
```

### Keyboard Shortcuts

- **Ctrl+O**: Open file
- **Ctrl+S**: Save file
- **Ctrl+K**: Focus command bar
- **Escape**: Focus editor
- **Ctrl+Q**: Quit application

### Commands

#### File Operations
- `/open <filename>` - Open a file
- `/save` - Save current file
- `/saveas <filename>` - Save as new file

#### AI Commands
- `/kimi <query>` - General AI query
- `/explain` - Explain selected code
- `/fix` - Fix issues in selected code
- `/refactor [requirements]` - Refactor selected code
- `/generate_test` - Generate unit tests
- `/doc` - Add documentation

#### Agent Mode
- `/run_agent <goal>` - Execute complex tasks with AI agent

#### Help
- `/help` - Show all available commands

### Example Workflows

#### 1. Code Explanation
1. Open a Python file: `/open example.py`
2. Select some code in the editor
3. Run: `/explain`
4. View the AI explanation in the output panel

#### 2. Code Fixing
1. Select problematic code
2. Run: `/fix`
3. Review the suggested fixes
4. Apply changes if appropriate

#### 3. Agent Mode for Complex Tasks
1. Run: `/run_agent "Refactor this code to use async/await and add error handling"`
2. The AI will:
   - Analyze the current code
   - Plan the refactoring steps
   - Use tools to make changes
   - Provide a summary of changes

#### 4. Test Generation
1. Select a function or class
2. Run: `/generate_test`
3. Review the generated tests
4. Save to a test file if needed

## Project Structure

```
k2edit/
├── main.py                 # Application entry point
├── editor.py               # Main editor widget
├── views/
│   ├── command_bar.py      # Command input handling
│   └── output_panel.py     # AI response display
├── agent/
│   ├── kimi_api.py         # Kimi API integration
│   ├── schema.py           # Tool schemas
│   └── tools.py            # Local tool implementations
├── styles.tcss             # UI styling
├── requirements.txt        # Dependencies
├── .env.example           # Environment template
└── README.md              # This file
```

## Configuration

### Environment Variables

- `KIMI_API_KEY`: Your Kimi API key (required)
- `KIMI_BASE_URL`: API base URL (default: https://api.moonshot.cn/v1)

### Customization

- **Themes**: Modify `styles.tcss` for custom colors and layout
- **Commands**: Add new commands in `views/command_bar.py`
- **Tools**: Extend tool capabilities in `agent/tools.py`
- **AI Prompts**: Customize prompts in command handlers

## API Integration Details

### Kimi-K2 Model
- Model: `kimi-k2-0711-preview`
- Temperature: 0.6 (optimized for code tasks)
- Tool calling: Enabled for agent mode
- Context window: 128k tokens

### Tool Calling
The editor supports these tools for AI agent mode:
- `read_file`: Read file contents
- `write_file`: Write to files
- `replace_code`: Replace code sections
- `insert_code`: Insert code at specific lines
- `list_files`: Directory listing
- `search_code`: Code pattern search
- `run_command`: Execute shell commands
- `analyze_code`: Code analysis

## Troubleshooting

### Common Issues

1. **API Key Error**
   - Ensure your `.env` file contains a valid `KIMI_API_KEY`
   - Check that the API key has sufficient credits

2. **Import Errors**
   - Install all dependencies: `pip install -r requirements.txt`
   - Ensure you're using Python 3.9+

3. **UI Issues**
   - Try resizing your terminal window
   - Ensure terminal supports colors and Unicode

4. **File Permission Errors**
   - Check file permissions for read/write operations
   - Ensure the editor has access to the target directories

## Releases and Binary Distribution

### GitHub Releases
Binary releases are automatically built and published when tags are pushed to the repository. The GitHub workflow creates cross-platform binaries for:
- Linux (x64)
- macOS (Intel and Apple Silicon)
- Windows (x64)

### Creating a Release
1. Tag your commit: `git tag v1.0.0`
2. Push the tag: `git push origin v1.0.0`
3. The GitHub workflow will automatically build and create a release

### Manual Binary Build
To build a binary locally using PyInstaller:
```bash
# Install PyInstaller
pip install pyinstaller

# Build using the spec file
pyinstaller k2edit.spec

# The binary will be in the dist/ directory
```

### Logging
Logs are stored in a cross-platform location:
- **Linux/macOS**: `~/k2edit/logs/k2edit.log`
- **Windows**: `%USERPROFILE%\k2edit\logs\k2edit.log`

### Debug Mode

For debugging, you can:
1. Check the output panel for error messages
2. Use `/kimi "debug this error: <error_message>"` for AI assistance
3. Review the terminal output for Python exceptions

## Contributing

Contributions are welcome! Areas for improvement:
- Additional language support
- More AI commands and tools
- Enhanced UI features
- Performance optimizations
- Additional themes

## License

This project is open source. Please ensure you comply with the Kimi API terms of service when using the AI features.

## Support

For issues related to:
- **Editor functionality**: Check this README and code comments
- **Kimi API**: Visit [Moonshot AI Documentation](https://platform.moonshot.ai/docs)
- **Textual framework**: Check [Textual Documentation](https://textual.textualize.io/)