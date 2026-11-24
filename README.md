# PolyLint

**A Python linter, static analyzer, and code formatter built from scratch.**

PolyLint is a lightweight Python code analysis tool designed to identify common coding issues, analyze source code, apply safe automatic fixes, and improve code readability through formatting.

Unlike tools that rely entirely on existing Python parsing libraries, PolyLint implements its own lexer, parser, Abstract Syntax Tree (AST), and semantic analysis pipeline.

## Features

### 1. Lexical Analysis
- Tokenizes Python source code.
- Recognizes identifiers, keywords, literals, operators, and punctuation.
- Handles indentation and newline tokens.
- Supports multiline expressions and line continuations.

### 2. Parsing
- Custom recursive-descent Python parser.
- Builds an Abstract Syntax Tree (AST).
- Supports functions, classes, decorators, imports, loops, and conditional statements.
- Supports comprehensions, lambda expressions, annotations, and asynchronous constructs.
- Supports structural pattern matching and modern Python syntax.

### 3. Static Analysis
- Detects unused imports and variables where supported.
- Identifies naming convention violations.
- Performs semantic checks using scope and symbol information.
- Reports diagnostics with source locations.

### 4. Automatic Fixes
- Automatically fixes selected linting issues.
- Supports unused-import removal.
- Provides a command-line autofix workflow.

### 5. Code Formatting
- Includes a Python source formatter.
- Improves code consistency and readability.

## Architecture

PolyLint follows a multi-stage source analysis pipeline:

```text
Python Source Code
        |
        v
     Lexer
        |
        v
     Tokens
        |
        v
     Parser
        |
        v
 Abstract Syntax Tree
        |
        v
 Semantic Analysis
        |
        v
   Rule Engine
        |
        v
   Diagnostics
        |
        v
  Automatic Fixes
```

## Project Structure

```text
polylint/
│
├── src/
│   └── polylint/
│       ├── languages/
│       │   └── python/
│       │       ├── lexer.py
│       │       ├── parser.py
│       │       ├── tokens.py
│       │       └── ast.py
│       │
│       ├── rules/
│       ├── semantic/
│       ├── formatter/
│       └── cli/
│
├── tests/
├── pyproject.toml
└── README.md
```

*The directory structure above is a simplified architectural overview.*

## Installation

Clone the repository:

```bash
git clone https://github.com/amul-yav/polylint.git
cd polylint
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the project in editable mode:

```bash
pip install -e .
```

## Usage

### Check a Python file

```bash
polylint check sample.py
```

### Automatically fix supported issues

```bash
polylint check sample.py --fix
```

### Format a Python file

```bash
polylint format sample.py
```

### Run the test suite

```bash
python -m pytest -q
```

## Technology Stack

- **Language:** Python
- **Parsing:** Custom Lexer and Recursive-Descent Parser
- **Representation:** Custom Abstract Syntax Tree
- **Analysis:** Semantic Analyzer and Rule Engine
- **Testing:** pytest
- **Interface:** Command-Line Interface (CLI)

## Current Status

PolyLint is an actively developed project.

The core Python analysis pipeline, linting rules, automatic fixes, and formatter are implemented. Python syntax support is being expanded incrementally.

The project has a reported test-suite milestone of **617 passing tests**.

### Known Limitations

- Python grammar compatibility is not yet complete.
- Some advanced syntax constructs are not supported.
- Semantic analysis has limitations around complex control flow and scope handling.
- Automatic fixes are available only for selected rules.
- Formatter coverage and edge-case handling are still evolving.

PolyLint should currently be considered a development-stage tool rather than a complete replacement for established Python linters.

## Future Improvements

- Improve Python grammar compatibility.
- Strengthen semantic analysis and scope resolution.
- Expand linting rules.
- Improve autofix safety and validation.
- Improve formatter consistency.
- Expand test coverage using real-world Python projects.

## Contributing

Contributions, bug reports, and suggestions are welcome.

If you find an issue or have an idea for improvement, feel free to open a GitHub issue.

## License

Add your chosen open-source license here before publishing.