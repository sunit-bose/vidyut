# PR Review Agent



**Tagline:** A self-hosted agent to help review your GitHub Pull Requests, identify impact areas, suggest improvements, and enhance your code quality workflow.

## Overview

<img width="499" height="491" alt="Screenshot 2025-07-18 at 11 09 24 AM" src="https://github.com/user-attachments/assets/9161d2ae-ccfa-4a01-b3ce-856ce9b90451" />  <img width="481" height="385" alt="Screenshot 2025-07-18 at 11 09 05 AM" src="https://github.com/user-attachments/assets/d49434a6-29db-4c53-ab00-f56267664cd1" />  <img width="354" height="177" alt="Screenshot 2025-07-18 at 11 08 17 AM" src="https://github.com/user-attachments/assets/a36ca084-1fc1-491f-b0ef-a62588883248" />


This project is an agent designed to assist developers and teams by automating parts of the Pull Request (PR) review process. It fetches PR details (including full file content for changed files) from GitHub, performs various analyses on these changes, and offers suggestions.

Key analyses include:
*   **Structural code analysis** for Python (AST) and Java (`javalang`) to identify new/modified functions, classes, and methods.
*   **Linting** for Python (Flake8) and Java (Checkstyle).
*   **Security scanning** for known sensitive keywords and risky patterns.
*   **Dependency analysis** for Maven `pom.xml` files.
*   **Test stub generation** for new Python and Java code.
*   **AI-Generated Code Detection:** An improved heuristic-based approach to detect potential AI-generated code.

The agent aims to provide helpful insights to reviewers and authors, streamline the review cycle, and improve code quality. It's run via a command-line interface (CLI) and can process multiple PRs concurrently, offering a summary of findings and detailed suggestions.

## Features

*   Fetches PR details (title, description, author, changed files, diffs) from GitHub.
*   Fetches the full content of changed files, enabling more accurate analysis.
*   Accepts multiple PR URLs for concurrent processing.
*   **Configurable Analysis Pipeline:** Choose which analyses to run via CLI.
*   **Python Analysis:**
    *   AST parsing for new/modified definitions (functions, classes, methods).
    *   Specific dependency notes and targeted unit test suggestions.
    *   Flake8 linting (configurable options via CLI using `--flake8-options`).
    *   Basic `unittest` stub generation for new definitions (stubs use `NotImplementedError` placeholders).
*   **Java Analysis:**
    *   `javalang` parsing for new/modified definitions.
    *   Specific dependency notes and targeted JUnit test suggestions.
    *   Checkstyle linting (customizable config file via CLI using `--checkstyle-config`, defaults to Google's Java Style Guide).
    *   Experimental: Generates basic JUnit 5 boilerplate (stubs) for newly defined public Java classes, interfaces, enums, and their public methods (enable with `--analyses all` or by including `java_test_stubs`). Stubs use `UnsupportedOperationException` as placeholders.
*   **Maven POM Analysis:** Identifies new/changed dependencies in `pom.xml`.
*   **Configurable Security Scanning:** Detects keywords and regex patterns defined in `config/security_keywords.json` within changed code lines of Python, Java, and other text files.
*   **Enhanced Console Reporting:** Provides a structured summary when processing multiple PRs, detailing successes, failures, and analyses with issues.
*   **Structured Suggestion Data:** Internal representation of suggestions is now structured (list of dictionaries), paving the way for future output formats (e.g., JSON, direct PR comments).

## Tech Stack

*   Python 3.9+
*   `requests`: For GitHub API interaction.
*   `javalang`: For Java code parsing.
*   `flake8`: For Python linting.
*   Checkstyle: For Java linting (external tool).
*   `pytest` & `pytest-mock`: For development testing.

## Prerequisites

*   Git
*   Python 3.9 or higher.
*   Java Runtime Environment (JRE version 8+) for Java linting with Checkstyle.

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
    This will install `flake8` and other necessary Python packages.

## Tool Setup

### Java Linting (Checkstyle)

1.  **JRE:** Ensure a JRE (version 8+) is installed and `java` is in your system's PATH.
2.  **Checkstyle JAR:**
    *   Download the Checkstyle JAR file (e.g., `checkstyle-X.Y-all.jar`) from the [Checkstyle GitHub releases page](https://github.com/checkstyle/checkstyle/releases).
    *   **Option 1 (Recommended):** Set the `CHECKSTYLE_JAR` environment variable to the full path of the downloaded JAR file.
        ```bash
        export CHECKSTYLE_JAR="/path/to/your/checkstyle-VERSION-all.jar"
        ```
    *   **Option 2:** Rename the JAR to `checkstyle.jar` and place it in a directory included in your system's PATH.
3.  **Configuration:** The agent uses `config/google_checks.xml` by default. You can override this using the `--checkstyle-config` CLI option.

### Python Linting (Flake8)

*   Flake8 is installed as a Python dependency.
*   It will automatically pick up standard Flake8 configuration files (e.g., `.flake8`, `setup.cfg`, `tox.ini`) if present in your project or user directory.
*   You can also pass specific Flake8 options via the `--flake8-options` CLI argument.

## Usage

To run the agent, use the `src.main` module and provide one or more GitHub Pull Request URLs:

```bash
python -m src.main <pr_url_1> [pr_url_2 ...] [OPTIONS]
```

**Example:**
```bash
python -m src.main https://github.com/owner/repo/pull/123
```

### Command-Line Options

*   **`pr_urls`** (Positional): One or more GitHub Pull Request URLs to review.
*   **`--analyses <types>`**: Comma-separated list of analyses to run.
    *   **Available:** `python_ast`, `flake8`, `checkstyle`, `java_parser`, `security_scan`, `python_test_stubs` (experimental), `java_test_stubs` (experimental), `maven_pom_analysis`.
    *   **Special values:**
        *   `all`: Runs all available analyses, including experimental ones.
        *   `none`: Skips all code analysis steps.
        *   `default`: Runs `python_ast`, `flake8`, `checkstyle`, `security_scan`, `java_parser`, `maven_pom_analysis`. (This is the behavior if `--analyses` is omitted).
    *   Example: `--analyses python_ast,flake8,security_scan`
*   **`--checkstyle-config <PATH>`**: Path to a custom Checkstyle configuration XML file. If not provided, uses the default (`config/google_checks.xml`).
    *   Example: `--checkstyle-config /path/to/my_checkstyle_rules.xml`
*   **`--flake8-options "<OPTIONS_STRING>"`**: Custom options string for Flake8, enclosed in quotes (e.g., `"--ignore E501,W503 --max-line-length=88"`). These are passed directly to the `flake8` command.
    *   Example: `--flake8-options "--ignore E203,W503 --max-doc-length=120"`

**Example with options:**
```bash
python -m src.main --analyses all --flake8-options "--max-doc-length=100" https://github.com/owner/repo/pull/123
```

### Interpreting Output

The agent processes each PR and prints:
1.  A header with the PR title and link.
2.  The status of the review for that PR:
    *   `❌ FAILED`: Critical error prevented processing.
    *   `⚠️ COMPLETED (with analysis issues)`: Analysis ran but some tools reported errors (e.g., linter misconfiguration, parser errors on malformed code).
    *   `✅ COMPLETED (No specific actionable suggestions generated)`: Analysis ran cleanly but no specific items were flagged.
    *   `✅ COMPLETED (Suggestions generated)`: Analysis ran cleanly and suggestions are available.
3.  A list of suggestions, categorized by type (e.g., linting, security, test stubs).
    *   `📄 File:` markers indicate which file the following suggestions pertain to.
    *   Suggestions include line numbers, severity, and messages where applicable.
    *   Test stubs are provided as code blocks.

After all PRs are processed, an **Overall Processing Summary** is displayed, tallying the outcomes.

### GitHub API Rate Limiting & Private Repositories

The agent makes calls to the GitHub API. For unauthenticated requests, GitHub imposes rate limits. For frequent use or private repositories, a GitHub Personal Access Token (PAT) is recommended.

*(Note: The agent currently does not have a direct command-line option or persistent configuration for tokens. To use a token with the current version, you would need to modify the `api_headers` in `src/pr_parser.py` (within `get_pr_details` and `get_file_content_at_ref`) to include the `Authorization` header, like `api_headers["Authorization"] = f"token YOUR_PAT_HERE"`. This will be improved in future versions.)*

## Customization

### Security Scan Configuration (`config/security_keywords.json`)

The security scan uses a JSON configuration file (`config/security_keywords.json`) to define patterns. You can customize this file:

*   **`keywords`**: A list of case-sensitive strings to find directly in changed lines.
*   **`patterns`**: A list of dictionaries, each defining a regular expression:
    *   `"name"`: A descriptive name for the pattern (used in suggestions).
    *   `"pattern"`: The regex string.

**Example `config/security_keywords.json`:**
```json
{
  "keywords": [
    "TODO:SECURITY",
    "FIXME:SECURITY",
    "HARDCODED_PASSWORD",
    "private_key"
  ],
  "patterns": [
    {
      "name": "Generic API Key Pattern",
      "pattern": "(api_key|apikey|api-key|client_secret|access_token)\\s*[:=]\\s*['\\\"]?[a-zA-Z0-9_\\-.~+/=]{20,}['\\\"]?"
    },
    {
      "name": "URL with Basic Auth Credentials",
      "pattern": "https?://[a-zA-Z0-9\\-_.~!$&'()*+,;=:%]+:[a-zA-Z0-9\\-_.~!$&'()*+,;=:%]+@[a-zA-Z0-9\\-_.~]+"
    }
  ]
}
```

### Checkstyle Linter Rules
The default Checkstyle configuration is `config/google_checks.xml`. You can edit this file directly for project-wide changes or provide a path to your own complete configuration using the `--checkstyle-config` CLI option.

### Flake8 Linter Rules
Flake8 behavior can be customized using standard Flake8 configuration files (e.g., `.flake8`, `setup.cfg`, `tox.ini`) in your project, or by passing specific options via the `--flake8-options` CLI argument.

## Architecture

An overview of the agent's architecture and design principles can be found in [docs/architecture.md](docs/architecture.md).

## Contributing

Contributions are welcome! Please open an issue to discuss bugs or feature ideas. Pull requests are also appreciated.

## License

This project is licensed under the MIT License. (See the `LICENSE` file for details).

## Future Roadmap (High-Level)

*   **Advanced Code Analysis:** Deeper static analysis (SAST, bug patterns), Software Composition Analysis (SCA).
*   **Sophisticated Suggestion Engine:** More actionable, context-aware, and prioritized suggestions.
*   **Configuration Management:** Improved handling for API keys, rule settings, etc.
*   **Platform Support:** Abstract PR parsing for GitLab, Bitbucket.
*   **Output Formats:** JSON, HTML reports, and potential integrations (e.g., Slack).
*   **Refined `async` Operations:** For better scalability with many PRs or large files.

(See the end of `README.md` in the source for a more detailed earlier roadmap if interested in prior thoughts).

### Interpreting the Output

The overall processing summary provides the following information:

*   **critically failed:** The number of pull requests that could not be processed due to a critical error.
*   **completed with analysis issues:** The number of pull requests that were processed, but with one or more analysis tools reporting an error.
*   **completed with no specific suggestions:** The number of pull requests that were processed successfully, but with no specific suggestions generated.
*   **completed cleanly with suggestions:** The number of pull requests that were processed successfully and have suggestions.

## CI/CD Integration

This utility can be integrated into your CI/CD pipeline to automatically review pull requests. Here are some examples for popular CI/CD platforms:

### Jenkins

```groovy
pipeline {
    agent any
    stages {
        stage('PR Review') {
            steps {
                script {
                    // Ensure the repository is checked out
                    checkout scm
                    // Run the PR review agent
                    sh 'python -m src.main ${env.CHANGE_URL}'
                }
            }
        }
    }
}
```

### GitHub Actions

```yaml
name: PR Review

on:
  pull_request:

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python 3.9
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run PR Review
        run: python -m src.main ${{ github.event.pull_request.html_url }}
```

### GitLab CI/CD

```yaml
stages:
  - review

pr_review:
  stage: review
  image: python:3.9
  script:
    - pip install -r requirements.txt
    - python -m src.main $CI_MERGE_REQUEST_PROJECT_URL/merge_requests/$CI_MERGE_REQUEST_IID
```

### Bitbucket Pipelines

```yaml
image: python:3.9

pipelines:
  pull-requests:
    '**':
      - step:
          name: PR Review
          script:
            - pip install -r requirements.txt
            - python -m src.main $BITBUCKET_PR_ID
```
