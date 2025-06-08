# Agent Architecture

This document provides a high-level overview of the AI PR Review Agent's architecture, outlining its main components and the flow of data.

## Core Components

The agent is primarily composed of the following Python modules located in the `src/` directory:

1.  **`main.py`**:
    *   **Entry Point:** Serves as the command-line interface (CLI) for the agent.
    *   **Argument Parsing:** Handles CLI arguments for PR URLs, analysis selection (`--analyses`), and linter configurations (`--checkstyle-config`, `--flake8-options`).
    *   **Concurrency:** Manages concurrent processing of multiple PRs using `concurrent.futures.ThreadPoolExecutor`.
    *   **Orchestration:** Initiates the review process for each PR by calling `pr_parser.py` and then `code_analyzer.py`.
    *   **Output Formatting:** Receives structured suggestions from `suggestion_generator.py` and formats them for console display, including a final summary of processing outcomes.

2.  **`pr_parser.py`**:
    *   **GitHub Interaction:** Responsible for all direct communication with the GitHub API.
    *   **PR Data Fetching:**
        *   `get_pr_details(pr_url)`: Fetches metadata for a pull request, including title, description, author, and a list of changed files with their diff/patch text.
        *   `get_file_content_at_ref(...)`: Fetches the full content of specific files from the repository at a given commit SHA (the PR's head SHA). This is crucial for accurate linting and parsing.
    *   **Data Extraction:** Extracts relevant information (e.g., owner, repo, head SHA, file paths, patch text) for use by other components.

3.  **`code_analyzer.py`**:
    *   **Analysis Hub:** Orchestrates various analysis tasks on the changed files of a PR.
    *   **Analysis Dispatch:** Based on file extensions (`.py`, `.java`, `pom.xml`) and the enabled analyses types, it calls specific private functions (e.g., `_analyze_python_file`, `_analyze_java_file`).
    *   **Language-Specific Analysis:**
        *   **Python:** Uses `ast` module for parsing, Flake8 for linting. Identifies new/modified definitions, generates dependency notes, test suggestions, and test stubs.
        *   **Java:** Uses `javalang` for parsing, Checkstyle for linting. Identifies new/modified definitions, generates dependency notes, test suggestions, and test stubs.
        *   **Maven `pom.xml`:** Uses `xml.etree.ElementTree` to parse and identify dependency changes.
    *   **Security Scanning:** Implements a configurable keyword and regex-pattern based security scan on patch text for all relevant file types. The configuration is loaded from `config/security_keywords.json`.
    *   **Configuration Handling:** Accepts and uses configuration for linters (Checkstyle config path, Flake8 options string).
    *   **Results Aggregation:** Collects findings from all enabled analyses for each file into a structured dictionary. These findings include impacts, linting issues, security concerns, identified code definitions, dependency notes, and test suggestions/stubs.

4.  **`suggestion_generator.py`**:
    *   **Structured Output Generation:** Takes the raw analysis results from `code_analyzer.py`.
    *   **Translation to Suggestions:** Transforms these findings into a list of structured suggestion dictionaries. Each dictionary has a `type` (e.g., "linting", "security_concern", "python_test_stub"), `file_path`, `line_number`, `message`, and other relevant details.
    *   **Formatting Logic (Implicit):** While it doesn't directly format for the console, it structures the data in a way that `main.py` can easily consume for presentation.

## Configuration Files (`config/`)

*   **`google_checks.xml`**: The default Checkstyle configuration file, based on Google's Java Style Guide.
*   **`security_keywords.json`**: A JSON file defining keywords and regex patterns used by the security scanner in `code_analyzer.py`.

## Data Flow

1.  **Input:** User provides PR URLs and optional CLI arguments (analyses to run, linter configs) to `main.py`.
2.  **PR Details Fetching:** `main.py` invokes `process_single_pr`, which calls `pr_parser.get_pr_details(pr_url)` to get PR metadata and changed file information.
3.  **Full File Content Fetching:** For each changed file, `code_analyzer.py` (via its sub-modules like `_analyze_python_file`) calls `pr_parser.get_file_content_at_ref(...)` to get the complete source code.
4.  **Code Analysis:** `main.py` (via `process_single_pr`) calls `code_analyzer.analyze_code_changes(pr_data, analyses_to_run, configs...)`.
    *   `code_analyzer.py` iterates through changed files.
    *   For each file, it dispatches to the appropriate analysis functions (`_analyze_python_file`, `_analyze_java_file`, etc.) based on file type and selected analyses.
    *   These functions perform parsing, linting, security scans, etc., and compile a list of findings.
5.  **Suggestion Generation:** The collected analysis findings are passed to `suggestion_generator.generate_suggestions(analysis_results)`. This function converts the raw findings into a list of structured suggestion dictionaries.
6.  **Output Display:** `main.py` receives the list of structured suggestions. It then iterates through them, formatting each one for display on the console. It also prints an overall summary of the review process for all PRs.

This modular architecture allows for easier extension and maintenance, with clear separation of concerns between fetching data, analyzing code, and generating suggestions.
