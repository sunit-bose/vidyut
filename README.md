# AI PR Review Agent

**Tagline:** A self-hosted AI agent to help review your GitHub Pull Requests, identify impact areas, and suggest improvements.

## Overview

This project is an AI-powered agent designed to assist developers and teams by automating parts of the Pull Request (PR) review process. It fetches PR details (including full file content for changed files) from GitHub, performs an initial analysis of these changes (with deeper inspection of Python code structure via AST parsing, and foundational support for Java, including linting), and offers suggestions related to potential impact areas, code reuse, design patterns (SOLID), unit tests, and security considerations. The agent is run via a command-line interface (CLI) and can process multiple PRs concurrently.

The goal is to provide helpful insights to reviewers and authors, streamline the review cycle, and improve code quality over time. While currently in its initial phase with foundational analysis logic, the long-term vision is to build a more sophisticated and configurable review assistant.

## Current Features (Phase 1)

*   Fetches PR details (title, description, author, changed files, diffs) from GitHub.
*   Fetches the full content of changed files from GitHub, enabling more accurate linting and future analysis.
*   Accepts multiple PR URLs for concurrent processing.
*   **Enhanced analysis for Python files:**
    *   Uses Abstract Syntax Tree (AST) parsing to identify functions, classes, and methods.
    *   Correlates AST information with PR changes to pinpoint **new or modified definitions**.
    *   Provides **specific dependency notes** highlighting the signatures and locations of these new/modified Python definitions.
    *   Generates **targeted unit test suggestions** for these specific new/modified functions, classes, and methods.
*   **Static analysis and foundational support for Java files:**
    *   Checkstyle integration for linting, operating on full file content.
    *   Basic structure awareness with general suggestions.
*   Rudimentary security keyword scanning in Python and Java code patches (e.g., for 'TODO:SECURITY', 'hardcoded_password').
*   Generic handling for other file types (e.g., Markdown, text).
*   Performs foundational analysis for overall PR context:
    *   Identifying modified files as general impact areas.
    *   Basic suggestions for code reuse if multiple files are changed (overall summary).
    *   Reminders for SOLID design principles (overall summary).
*   Generates a list of suggestions, including general reminders for unit testing and security, plus file-specific points from linters, AST analysis, and scans.
*   Command-line interface (CLI) to initiate reviews and display results.
*   Basic unit test coverage for core modules.

## Tech Stack

*   Python 3.x
*   `requests`: For making HTTP requests to the GitHub API.
*   `pytest`: For unit testing.
*   `pytest-mock`: For mocking in tests.
*   `javalang`: For basic parsing of Java code structure (foundational, used alongside Checkstyle).
*   `flake8`: For Python linting.
*   Checkstyle: For Java linting (external tool, see Tool Setup).

## Prerequisites

*   Git
*   Python 3.7+ (or as per your environment's Python 3 version)
*   Java Runtime Environment (JRE) for Java linting (see Tool Setup).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <your_repository_url>
    # Replace <your_repository_url> with the actual URL of this project's repository
    cd <repository_directory_name>
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Tool Setup

### Java Linting Setup (Checkstyle)

To enable Java linting with Checkstyle, you need to have the following set up in your environment:

1.  **Java Runtime Environment (JRE):** A JRE (version 8 or higher recommended) must be installed and its `java` command accessible.
2.  **Checkstyle JAR:** Download the Checkstyle JAR file (e.g., `checkstyle-X.Y-all.jar`). You can find the latest releases on the [Checkstyle GitHub releases page](https://github.com/checkstyle/checkstyle/releases).
    *   The agent attempts to run Checkstyle by invoking `java -jar <path_to_checkstyle.jar> ...`.
    *   You can make the Checkstyle JAR accessible by:
        *   Placing it in a directory that's part of your system's `PATH` and renaming the JAR to `checkstyle.jar`.
        *   Setting the `CHECKSTYLE_JAR` environment variable to the full path of the JAR file (e.g., `export CHECKSTYLE_JAR=/path/to/your/checkstyle-10.3.2-all.jar`).
3.  **Configuration:** The agent includes a default Checkstyle configuration based on Google's Java Style Guide, located at `config/google_checks.xml`. For custom checks, you would modify this file or use a mechanism (to be implemented in future versions) to specify a custom configuration file path.

## Usage

To run the agent, provide one or more GitHub Pull Request URLs:

```bash
python -m src.main <pr_url_1> [pr_url_2 ...]
```

For example:
```bash
python -m src.main https://github.com/owner/repo/pull/123 https://github.com/owner/repo/pull/456
```

Ensure necessary dependencies are installed (as per the Installation section) and tools are set up (see Tool Setup). The agent will process these PRs concurrently (up to a default limit of 4) and display the review suggestions for each.

### GitHub API Rate Limiting & Private Repositories

The agent makes calls to the GitHub API. For unauthenticated requests, GitHub imposes rate limits. If you are analyzing many PRs, large PRs with many files, or private repositories, you may encounter these limits or require authentication.

To use a GitHub Personal Access Token (PAT):
*   Generate a PAT from your GitHub account with appropriate permissions (e.g., `repo` scope for private repositories).
*   *(Note: The agent currently does not have a direct command-line option or configuration file setting for tokens. To use a token with the current version, you would need to modify the `api_headers` in `src/code_analyzer.py` (within `_analyze_python_file` and `_analyze_java_file` when `get_file_content_at_ref` is called) to include the `Authorization` header, like `api_headers["Authorization"] = f"token YOUR_PAT_HERE"`. Secure token management via configuration will be improved in future versions.)*

## Contributing

Contributions are welcome! If you have suggestions for improvements or new features, or if you encounter any bugs, please open an issue on the project's GitHub page to discuss them. Pull requests are also appreciated.

## License

This project is licensed under the MIT License. (See the `LICENSE` file for details).

## Future Roadmap

This project aims to evolve into a comprehensive and intelligent PR review assistant. Here are some of  the planned enhancements and architectural considerations for future development:

### Core Functionality Enhancements
*   **Advanced Code Analysis:**
    *   **SOLID Principles:** Implement checks for adherence to SOLID design principles.
    *   **Security Vulnerabilities:** Integrate more sophisticated security vulnerability detection (e.g., common CWEs, dependency checking).
    *   **Code Reuse & Duplication:** Introduce robust algorithms for identifying duplicated code and suggesting abstractions.
    *   **Custom Rules Engine:** Allow users to define custom rules and checks specific to their project or organization.
*   **Sophisticated Suggestion Engine:**
    *   Move beyond direct reporting of analysis findings to provide more actionable, context-aware, and prioritized suggestions.
    *   Potentially incorporate a rules engine or simple ML models for ranking suggestions.

### Architectural & Technical Improvements
*   **Configuration Management:** Implement a system for managing configurations (e.g., API keys for private repos, analysis rule settings, output preferences) via configuration files or environment variables, including for the GitHub token and Checkstyle JAR path.
*   **Scalability & Performance:**
    *   **Asynchronous Operations:** Transition core I/O-bound operations (like API calls) to use `asyncio` and `aiohttp` for improved performance, especially under higher load.
    *   **Caching:** Implement caching for API responses and potentially for analysis results of unchanged code sections to reduce redundant processing and API calls.
    *   **Job Queues:** For scaling beyond a few concurrent PRs, integrate a job queue system (e.g., Celery, RQ) to manage and distribute review tasks.
*   **Input/Output Abstractions:**
    *   **Multi-Platform Git Support:** Abstract the PR parsing logic to support other Git hosting platforms (e.g., GitLab, Bitbucket) in addition to GitHub.
    *   **Flexible Output Formats:** Enable suggestions to be delivered in various formats (e.g., JSON, HTML) and to different destinations.
    *   **Slack Integration:** Send review summaries and critical suggestions directly to specified Slack channels.
*   **Structured Logging:** Replace basic `print` statements for internal logging with a robust logging framework (e.g., Python's `logging` module) for better debugging and traceability.
*   **Enhanced Concurrency:** While initial concurrency for 3-4 PRs will be added, further work will focus on scaling this efficiently.

### Testing & Quality Assurance
*   **Integration Tests:** Develop integration tests to verify the interactions between different modules.
*   **End-to-End Tests:** Create end-to-end tests using a dedicated test repository to simulate real-world PR review scenarios.

Contributions and suggestions for this roadmap are welcome!
