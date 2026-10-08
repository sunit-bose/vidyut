# PR Review Agent
<img width="1024" height="1024" alt="ChatGPT Image Jul 18, 2025, 11_06_38 AM" src="https://github.com/user-attachments/assets/6eca882e-6dfe-47e8-b34b-21a9f45eaee2" />



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
*   **AI-Generated Code Detection:** A heuristic-based approach to detect potential AI-generated code, including named-tool/vendor signals (Copilot, Tabnine, **Claude/Anthropic**, ChatGPT/OpenAI, Gemini, Jules, etc.) and common commit-attribution trailers (e.g. `Co-Authored-By: Claude <noreply@anthropic.com>`, `Generated with Claude Code`). This is **informational only** — see the note under [AI-Generated Code Detection](#ai-generated-code-detection) below.
*   **React/JS/TS Analysis:** A heuristic-based approach to React code: functional/class component detection with change tracking, hook usage (built-in and custom), and anti-pattern checks (missing `key` prop in list rendering, direct `this.state` mutation, `useEffect` missing a dependency array).
*   **GitHub PR Integration:** Can authenticate to the GitHub API via a token and post a single consolidated review comment back onto the PR — see [CI/CD Integration](#cicd-integration).

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
*   **React/JS/TS Analysis:**
    *   Detects functional components (`const Foo = (props) => ...`) and class components (`class Foo extends React.Component`), tracking whether each is new or modified based on the PR's diff hunks (same approach as the Python/Java analyzers).
    *   Detects hook usage, both built-in (`useState`, `useEffect`, ...) and custom (any `useXxx(...)` call).
    *   Flags likely anti-patterns: list items rendered via `.map()` without a `key` prop, direct mutation of `this.state`, and `useEffect` calls missing a dependency array.
    *   Runs the same configurable security keyword/pattern scan as Python/Java on `.js`/`.jsx`/`.ts`/`.tsx` patches.
    *   Enabled by default (part of `--analyses default`); disable/select explicitly via the `react_analysis` analysis type.
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
*   **`--github-token <TOKEN>`**: A GitHub token (PAT, or the Actions-provided `GITHUB_TOKEN`) used to authenticate all GitHub API requests. Defaults to the `GITHUB_TOKEN` environment variable if set. Required for private repositories and for `--post-comment`; strongly recommended in CI to avoid unauthenticated rate limits.
*   **`--post-comment`**: Posts a single consolidated Markdown summary comment on each reviewed PR. Requires `--github-token` (or `GITHUB_TOKEN`) with `pull-requests: write` permission.
*   **`--fail-on <types>`**: Comma-separated suggestion type(s) that cause the command to exit non-zero (e.g. to fail a CI check). Default: `security_concern`. Use `none` to never fail based on findings (a critical processing error still fails the run regardless).
    *   Other usable values include `react_issue`, `linting`, `pom_dependency_change`, etc. — any `type` emitted by the suggestion generator.
    *   **`ai_generated_code` can never be included here.** AI-generated-code detection is informational only, by design, and will never fail the build no matter how high its confidence score — see [AI-Generated Code Detection](#ai-generated-code-detection).
    *   Example: `--fail-on security_concern,react_issue`

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

The agent makes calls to the GitHub API. For unauthenticated requests, GitHub imposes low rate limits. For frequent use, private repositories, or posting comments back to a PR, pass a GitHub token via `--github-token <TOKEN>` or the `GITHUB_TOKEN` environment variable (GitHub Actions sets this automatically — see [CI/CD Integration](#cicd-integration)).

### AI-Generated Code Detection

`_detect_ai_generated_code` (in `src/code_analyzer.py`) is a **heuristic**, not a certainty check. It looks for two independent signals in a file's diff:

1.  **Named AI tool/vendor mentions** (confidence 0.9) — e.g. `Copilot`, `Tabnine`, `Claude`, `Anthropic`, `ChatGPT`, `OpenAI`, `Gemini`, `Jules`.
2.  **Attribution patterns** (confidence 0.85) commonly left by AI coding assistants, e.g. `Co-Authored-By: Claude <noreply@anthropic.com>`, `Generated with Claude Code`, or generic `AI-generated`/`AI-assisted` markers.
3.  A weak fallback heuristic (confidence 0.5) flags an unusually large number of newly *added* comment lines in a single patch.

**This finding is informational only.** It is surfaced in the console output, the structured suggestions (`type: "ai_generated_code"`), and the posted PR comment, but it can never fail a CI run — `ai_generated_code` is excluded from `--fail-on` even if explicitly requested. The intent is to flag likely AI-authored changes for a human reviewer's awareness, not to gate merges on an inherently fuzzy signal.

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

A ready-to-use workflow is included at [`.github/workflows/pr-review.yml`](.github/workflows/pr-review.yml). It:

*   Triggers on `pull_request` (opened/synchronize/reopened).
*   Installs Python + a JRE (for Checkstyle) and the project's dependencies.
*   Runs the agent with `--analyses all --post-comment --fail-on security_concern`, authenticated with the Actions-provided `GITHUB_TOKEN`.
*   Grants the job `pull-requests: write` so it can post the consolidated review comment, per the policy described in `--post-comment`/`--fail-on` above.

```yaml
name: PR Review Agent

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  pull-requests: write # Required to post the summary comment back onto the PR.
  contents: read

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.9"
      - uses: actions/setup-java@v4 # For Checkstyle/Java analysis
        with:
          distribution: "temurin"
          java-version: "17"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run PR Review Agent
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python -m src.main "${{ github.event.pull_request.html_url }}" \
            --analyses all \
            --post-comment \
            --fail-on security_concern
```

Devops notes:

*   **Failure policy** is deliberately asymmetric: `security_concern` findings (and any critical processing error) fail the check; `ai_generated_code` findings never do, regardless of confidence — they're surfaced in the posted comment for human awareness only. Tune which types fail the build via `--fail-on` (comma-separated), e.g. `--fail-on security_concern,react_issue`.
*   No extra secret setup is needed for public repos in the same org/repo — the default `GITHUB_TOKEN` Actions provides already has the right scope once `permissions.pull-requests: write` is set on the job.
*   For other CI platforms (Jenkins/GitLab/Bitbucket below), pass an equivalent token through `--github-token` (or `GITHUB_TOKEN` env var) and add `--post-comment --fail-on security_concern` the same way.

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
