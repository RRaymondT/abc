# Codebase Knowledge Graph Generator

## Overview

This project scans a software codebase, builds a knowledge graph from the identified files, technologies, and code structures, and then allows for this graph to be visualized in a web browser or exported as a Markdown summary suitable for Large Language Model (LLM) analysis.

The primary goal is to provide insights into the architecture, dependencies, and key components of a software project, facilitating understanding, documentation, and further automated analysis.

## Key Features

*   **Technology Identification:** Scans for project files (e.g., `pom.xml`, `package.json`, `requirements.txt`) and keywords within files to identify the technology stack (e.g., Maven, NPM, Python, Camunda, Spring).
*   **Python Code Parsing:** Utilizes Abstract Syntax Trees (AST) to parse Python files, extracting information about classes, methods, functions, imports, calls, and decorators.
*   **C# Parsing (Basic):** Extracts namespaces, `using` directives, class definitions (name, attributes, base types), interface definitions, method signatures (name, attributes, return type, parameters), and property definitions from `.cs` files.
*   **Vue.js SFC Parsing (Basic):** Parses `.vue` files to extract information from `<template>` (component usage, event bindings), `<script>` (component name, script language, imports, props, data object keys, method names, computed property names), and `<style>` (style language).
*   **BPMN Parsing:** Extracts key elements from Camunda BPMN 2.0 XML files, such as processes, service tasks (with implementation details), and user tasks.
*   **Graph Construction:** Builds a directed graph using the `networkx` library, representing files, code elements, technologies, and their relationships.
*   **Interactive Visualization:** Launches a Flask web server to display the graph using Vis.js, allowing for interactive exploration of nodes and edges.
*   **Markdown Export for LLMs:** Generates a structured Markdown summary of the graph, suitable for input into Large Language Models. This export can be filtered to focus on main project entities and specific codebase paths.
*   **Command-Line Interface:** Provides a CLI for easy operation, with options to control input, output mode, and various parameters.

## Setup and Installation

### Prerequisites

*   Python 3.7+

### 1. Clone the Repository (if applicable)

If you have obtained the code as a ZIP file, extract it. If it's a Git repository:
```bash
git clone <repository_url>
cd knowledge-graph-app
```

### 2. Create and Activate a Virtual Environment (Recommended)

*   **Unix/macOS:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
*   **Windows:**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```

### 3. Install Dependencies

Ensure your virtual environment is activated, then navigate to the `knowledge_graph_app` directory (if you cloned it) and run:

```bash
pip install -r requirements.txt
```

## How to Run

The application is run via `main.py` from within the `knowledge_graph_app` directory.

### Basic Syntax

```bash
python main.py <path_to_your_codebase> [options]
```

### Examples

1.  **Launch the Web Visualization (Default Mode):**
    ```bash
    python main.py /path/to/your/codebase
    ```
    This will typically start the server at `http://127.0.0.1:5000`. Open this address in your web browser.

2.  **Generate LLM Markdown Summary:**
    ```bash
    python main.py /path/to/your/codebase --output_mode llm_markdown
    ```
    This will create `knowledge_graph_summary.md` in the directory where you ran the command.

### Key Optional Arguments

*   `--output_mode {view,llm_markdown}`: Choose between web visualization (`view`) or Markdown export (`llm_markdown`). Default is `view`.
*   `--llm_output_file <filename.md>`: Specify the output file for the Markdown summary. Default: `knowledge_graph_summary.md`.
*   `--llm_filter_main_entities`: If set, the LLM Markdown export will primarily include code entities (files, classes, functions, BPMN elements) that are part of the analyzed codebase path. This helps in focusing the summary on the core project components rather than all linked external modules or generic technology references.
*   `--max_files_parse <number>`: An optional integer to limit the maximum number of files to parse. This can be useful for very large codebases to speed up initial analysis or for quick overview scans.
*   `--port <port_number>`: Set a custom port for the visualization web server. Default: `5000`.
*   `--host <host_address>`: Set a custom host address for the visualization web server. Default: `127.0.0.1`.

### Getting Help

To see all available command-line options and their descriptions:

```bash
python main.py --help
```

## Project Structure

```
knowledge_graph_app/
├── src/                      # Core application logic modules
│   ├── tech_scanner.py       # Technology identification logic
│   ├── code_parser.py        # File parsing (Python AST, BPMN XML)
│   ├── graph_builder.py      # Knowledge graph construction with networkx
│   ├── visualizer.py         # Web visualization (Flask + Vis.js)
│   ├── llm_export.py         # Markdown export for LLMs
│   └── templates/
│       └── index.html        # HTML template for the web visualizer
├── tests/                    # Unit tests for the modules
│   ├── __init__.py
│   ├── test_tech_scanner.py
│   ├── test_code_parser.py
│   └── test_graph_builder.py
├── main.py                   # Main Command-Line Interface (CLI) entry point
├── requirements.txt          # Python package dependencies
└── README.md                 # This file: project documentation
```

## Modules Overview

*   **`src/tech_scanner.py`**: Identifies technologies (e.g., Maven, Spring, Camunda) and project configuration files (e.g., `pom.xml`, `package.json`) by scanning filenames and file content for specific keywords and patterns.
*   **`src/code_parser.py`**: Parses source files to extract structural information. Supports Python (including decorators), C# (basic constructs), and Vue.js SFCs.
*   **`src/graph_builder.py`**: Constructs the knowledge graph using `networkx`, processing entities from Python, C#, Vue.js, BPMN, and technology scans.
*   **`src/visualizer.py`**: Handles the web-based visualization of the graph. It uses Flask to serve an HTML page and `export_graph_to_json` to convert the `networkx` graph into a JSON format suitable for the Vis.js library, which then renders the interactive graph in the browser.
*   **`src/llm_export.py`**: Generates Markdown summaries of the graph, including details for Python, C#, and Vue.js entities.
*   **`src/templates/index.html`**: The HTML template used by `visualizer.py`. It includes the Vis.js library and JavaScript code to fetch graph data from the Flask backend and render it.

## Current Limitations & Future Enhancements

### Parsing
*   **C# and Vue.js Parsers:** The C# and Vue.js parsers are regex-based and primarily target common declarative patterns. They do not build full Abstract Syntax Trees (ASTs) and thus have a limited semantic understanding of the code (e.g., for complex type resolution or detailed call graph analysis within C# methods or JavaScript/TypeScript in Vue components).
*   **Python Parsing:** Decorator extraction records the presence of decorators but does not analyze their runtime effects on the decorated entities. Call linking is primarily name-based and within the scope of a single file. Full cross-file call resolution and resolving calls to external libraries accurately is complex and not fully implemented.
*   **BPMN:** Basic element extraction for Camunda processes, service tasks, and user tasks.

### Scalability
*   **Large Codebases:** Performance might degrade on extremely large codebases due to the number of files to scan and parse. The `--max_files_parse` argument is a current workaround to limit processing time.
*   **Memory Usage:** Storing the full AST or parsed data for many files can be memory-intensive.

### Visualization
*   **Graph Clutter:** Very large graphs can become cluttered in the Vis.js visualization, making them hard to navigate.
*   **Layout Algorithms:** The default layout might not always be optimal for all graph structures.

### Error Handling
*   Error handling is basic. Complex or malformed code structures might lead to parsing errors or incomplete graph data.

### Future Enhancements
*   **More Robust Parsing:** Improve parsing for C# and JavaScript/TypeScript (within Vue SFCs), potentially by integrating with external tools (e.g., Roslyn for C#, Babel/ESLint for JS/TS) or dedicated libraries for deeper and more accurate analysis.
*   **Semantic Analysis:** Introduce semantic analysis capabilities, such as basic type resolution across supported languages and more accurate inter-file call graph construction.
*   **Expanded Language Support:** Implement more sophisticated parsers for other common languages (e.g., Java).
*   **Deeper Static Analysis (Python, C#, etc.):**
    *   Data flow analysis.
    *   Identification of design patterns or anti-patterns.
*   **Configuration File Parsing:** Extracting information from Spring XML/Java config, Kubernetes YAMLs, etc.
*   **Database Schema Parsing:** Incorporating database table structures and relationships from SQL DDL or ORM definitions.
*   **Incremental Analysis:** Ability to update the graph from changed files without re-processing the entire codebase.
*   **Advanced Visualization Features:**
    *   Filtering and searching directly in the UI.
    *   Different layout algorithms selectable by the user.
    *   Theming and customization.
*   **Plugin System:** Allow for easier addition of new parsers and analysis modules.
*   **Integration with IDEs:** Potential for plugins in IDEs to display graph information.

## Running Tests

To run the unit tests, navigate to the root directory of the project (`knowledge_graph_app/`) and execute:

```bash
python -m unittest discover -s tests -p "test_*.py"
```
This command will discover and run all test files (matching `test_*.py`) within the `tests` directory. Ensure that `requirements.txt` (which might include testing libraries if specified, though current ones are standard) are installed in your environment.
