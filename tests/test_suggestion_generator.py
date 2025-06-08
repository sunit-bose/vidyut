import pytest
from src.suggestion_generator import generate_suggestions
from src.code_analyzer import ( # Import constants for mock data
    ANALYSIS_PYTHON_AST, ANALYSIS_FLAKE8, ANALYSIS_JAVA_CHECKSTYLE,
    ANALYSIS_SECURITY_KEYWORD_SCAN, ANALYSIS_PYTHON_TEST_STUB_GEN
)

def test_generate_suggestions_input_none(capsys):
    result_none = generate_suggestions(None)
    assert result_none == []
    captured_none = capsys.readouterr()
    assert "Error: No analysis results provided for suggestion generation." in captured_none.out

def test_generate_suggestions_completely_empty_analysis():
    analysis_results = {
        'overall_summary': {
            'reuse_suggestions': [], 'solid_violations': [], 'general_security_reminders': []
        },
        'file_specific_findings': []
    }
    result = generate_suggestions(analysis_results)
    assert result == ["No specific suggestions based on the current analysis. General best practices still apply."]

def test_generate_suggestions_only_overall_summary():
    analysis_results = {
        'overall_summary': {
            'reuse_suggestions': ['Overall: Consider abstracting common utilities.'],
            'solid_violations': ['Overall: Check for SRP violations.'],
            'general_security_reminders': ['Overall: Remember to validate all inputs.']
        },
        'file_specific_findings': []
    }
    result = generate_suggestions(analysis_results)
    assert "Overall Code Reuse: Overall: Consider abstracting common utilities." in result
    assert "Overall Design Pattern: Overall: Check for SRP violations." in result
    assert "Overall: Remember to validate all inputs." in result
    assert len(result) == 3

def test_generate_suggestions_with_new_structure_and_security():
    mock_analysis = {
        'overall_summary': {
            'reuse_suggestions': ['Overall: Abstract common patterns.'],
            'solid_violations': ['Overall: Review Liskov Substitution Principle.'],
            'general_security_reminders': ['Overall: Sanitize external data.']
        },
        'file_specific_findings': [
            {
                'file_path': 'src/utils.py', 'language': 'python',
                'impacts': ['Python file src/utils.py was modified significantly.'],
                'dependencies': ['Dependency: `helper_func` might be affected.'],
                'tests_suggestions': ['Testing: Add unit tests for new logic in `utils.py`.'],
                'security_issues': ["Potential security keyword 'HARDCODED_PASSWORD' found in changes."],
                'linting_issues': [{'line': 10, 'column': 5, 'code': 'E302', 'message': 'expected 2 blank lines'}],
                'python_definitions': [],
                'python_test_stubs': []
            },
            {
                'file_path': 'com/myapp/Main.java', 'language': 'java',
                'impacts': ['Java file com/myapp/Main.java was added.'],
                'dependencies': [],
                'tests_suggestions': ['Testing: Ensure JUnit tests cover `Main.java`.'],
                'security_issues': [],
                'linting_issues': [{'line': 5, 'column': 1, 'code': 'MissingJavadoc', 'message': 'Missing Javadoc comment.', 'severity': 'info'}]
            },
            { 'file_path': 'docs/guide.md', 'language': 'other', 'impacts': ['Docs changed.'] }
        ]
    }
    suggestions = generate_suggestions(mock_analysis)

    # Flatten for easier checking of overall/general items
    output_str_full = "\n".join(suggestions)
    assert "Overall Code Reuse: Overall: Abstract common patterns." in output_str_full
    assert "Overall Design Pattern: Overall: Review Liskov Substitution Principle." in output_str_full
    assert "Overall: Sanitize external data." in output_str_full

    # --- Verify Python File (src/utils.py) ---
    py_utils_header = "--- File: src/utils.py (python) ---"
    assert py_utils_header in suggestions
    py_utils_idx = suggestions.index(py_utils_header)
    # Determine the end of this section
    next_header_idx_after_py = len(suggestions)
    for i in range(py_utils_idx + 1, len(suggestions)):
        if suggestions[i].startswith("--- File:"):
            next_header_idx_after_py = i
            break
    py_file_suggestions_slice = suggestions[py_utils_idx + 1 : next_header_idx_after_py]

    assert any("Impact: Python file src/utils.py was modified significantly." in s for s in py_file_suggestions_slice)
    assert any("Dependency Note: Dependency: `helper_func` might be affected." in s for s in py_file_suggestions_slice)
    assert any("Testing Suggestion: Testing: Add unit tests for new logic in `utils.py`." in s for s in py_file_suggestions_slice)
    assert any("Security Concern: Potential security keyword 'HARDCODED_PASSWORD' found in changes." in s for s in py_file_suggestions_slice)
    assert any("Linting Issues (python - Flake8):" in s for s in py_file_suggestions_slice)
    assert any("L10:5 [E302] expected 2 blank lines" in s for s in py_file_suggestions_slice)

    # --- Verify Java File (com/myapp/Main.java) ---
    java_main_header = "--- File: com/myapp/Main.java (java) ---"
    assert java_main_header in suggestions
    java_main_idx = suggestions.index(java_main_header)
    next_header_idx_after_java = len(suggestions)
    for i in range(java_main_idx + 1, len(suggestions)):
        if suggestions[i].startswith("--- File:"):
            next_header_idx_after_java = i
            break
    java_file_suggestions_slice = suggestions[java_main_idx + 1 : next_header_idx_after_java]

    assert any("Impact: Java file com/myapp/Main.java was added." in s for s in java_file_suggestions_slice)
    assert not any("Dependency Note:" in s for s in java_file_suggestions_slice)
    assert any("Testing Suggestion: Testing: Ensure JUnit tests cover `Main.java`." in s for s in java_file_suggestions_slice)
    assert any("Linting Issues (java - Checkstyle):" in s for s in java_file_suggestions_slice)
    assert any("L5:1 [MissingJavadoc] Missing Javadoc comment. (Severity: info)" in s for s in java_file_suggestions_slice)
    assert not any("Security Concern:" in s for s in java_file_suggestions_slice)

    # --- Verify Other File (docs/guide.md) ---
    md_guide_header = "--- File: docs/guide.md (other) ---"
    assert md_guide_header in suggestions
    md_guide_idx = suggestions.index(md_guide_header)
    next_header_idx_after_md = len(suggestions)
    # This assumes docs/guide.md is the last file in mock_analysis. Adjust if more files are added after it.
    # If there were other files, we'd find the next "--- File:" index.

    md_file_suggestions_slice = suggestions[md_guide_idx + 1 : next_header_idx_after_md]
    assert any("Impact: Docs changed." in s for s in md_file_suggestions_slice)
    assert not any("Dependency Note:" in s for s in md_file_suggestions_slice), "Dependency notes found for 'other' file type"
    assert not any("Testing Suggestion:" in s for s in md_file_suggestions_slice), "Testing suggestions found for 'other' file type"
    assert not any("Security Concern:" in s for s in md_file_suggestions_slice), "Security concerns found for 'other' file type"
    assert not any("Linting Issues:" in s for s in md_file_suggestions_slice), "Linting issues found for 'other' file type"
    assert not any("Generated Python Test Stubs:" in s for s in md_file_suggestions_slice), "Test stubs found for 'other' file type"


def test_generate_suggestions_with_python_test_stubs():
    mock_stub = {
        'target_definition_name': 'sample_func',
        'target_definition_type': 'function',
        'suggested_test_filename': 'tests/test_sample.py',
        'stub_code': 'import unittest\nclass TestSample_func(unittest.TestCase):\n    def test_basic(self): self.fail("TODO")'
    }
    mock_analysis_py_file_with_stubs = {
        'file_path': 'src/sample.py', 'language': 'python',
        'impacts': ['New Python file added.'],
        'dependencies': ["New Function `sample_func()` in src/sample.py. Review usage."],
        'tests_suggestions': ["New function `sample_func()` detected. Recommend tests."],
        'security_issues': [], 'linting_issues': [], 'python_definitions': [],
        'python_test_stubs': [mock_stub]
    }
    analysis_results = {
        'overall_summary': {},
        'file_specific_findings': [mock_analysis_py_file_with_stubs]
    }
    suggestions = generate_suggestions(analysis_results)
    output_str = "\n".join(suggestions)

    assert "--- File: src/sample.py (python) ---" in output_str
    assert "Generated Python Test Stubs:" in output_str
    assert "For new function `sample_func` (in src/sample.py):" in output_str
    assert "Suggested Test File: `tests/test_sample.py`" in output_str
    assert "```python\nimport unittest" in output_str
    assert "(Note: These are basic stubs. Please review, adjust paths, and implement test logic.)" in output_str

def test_generate_suggestions_other_file_no_impact():
    analysis_results = {
        'overall_summary': {},
        'file_specific_findings': [
            {'file_path': 'data.json', 'language': 'other', 'impacts': []}
        ]
    }
    suggestions = generate_suggestions(analysis_results)
    json_header = "--- File: data.json (other) ---"
    assert json_header in suggestions
    json_idx = suggestions.index(json_header)
    assert "No specific findings for this file." in suggestions[json_idx + 1]
