import pytest
from src.suggestion_generator import generate_suggestions
# Import constants if needed for constructing detailed mock_analysis data
from src.code_analyzer import (
    ANALYSIS_PYTHON_AST, ANALYSIS_FLAKE8, ANALYSIS_JAVA_CHECKSTYLE,
    ANALYSIS_JAVA_PARSER, ANALYSIS_SECURITY_KEYWORD_SCAN,
    ANALYSIS_PYTHON_TEST_STUB_GEN, ANALYSIS_MAVEN_POM
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

def test_generate_suggestions_with_detailed_java_pom_and_python_stubs():
    mock_analysis = {
        'overall_summary': {
            'reuse_suggestions': ['Overall: Refactor common logic.'],
            'solid_violations': ['Overall: Adhere to SOLID.'],
            'general_security_reminders': ['Overall: Check inputs.']
        },
        'file_specific_findings': [
            { # Python file with stubs
                'file_path': 'src/utils.py', 'language': 'python',
                'impacts': ['Python file modified.'],
                'dependencies': ['Modified Function `util_func(arg1)` in src/utils.py. Review impacts.'],
                'tests_suggestions': ['Modified function `util_func(arg1)` detected. Review tests.'],
                'security_issues': [], 'linting_issues': [], 'python_definitions': [],
                'python_test_stubs': [{
                    'target_definition_name': 'new_helper', 'target_definition_type': 'function',
                    'suggested_test_filename': 'tests/test_utils.py',
                    'stub_code': 'import unittest\n# ... stub for new_helper ...'
                }]
            },
            { # Java file with detailed suggestions
                'file_path': 'com/example/MyClass.java', 'language': 'java',
                'impacts': ['Java file modified.'],
                'dependencies': ["Modified public method `getItems(String filter)` (declared line 15) in com/example/MyClass.java. Consider impact..."],
                'tests_suggestions': ["Modified public method `getItems(String filter)` (declared line 15) detected in com/example/MyClass.java. Recommend reviewing JUnit tests..."],
                'linting_issues': [{'line': 5, 'column': 1, 'code': 'JavadocPackage', 'message': 'Missing package-info.java file.', 'severity': 'info'}],
                'security_issues': [], 'java_definitions': []
            },
            { # POM file example
                'file_path': 'pom.xml', 'language': 'maven_pom',
                'impacts': ['pom.xml was modified.'],
                'build_dependency_changes': [
                    "Potentially 1 new/modified <dependency> block(s) added/changed in pom.xml.",
                ],
                'dependencies': [], 'tests_suggestions': [], 'security_issues': [], 'linting_issues': []
            },
            { 'file_path': 'README.md', 'language': 'other', 'impacts': ['Docs changed.'] }
        ]
    }
    suggestions = generate_suggestions(mock_analysis)
    output_str = "\n".join(suggestions)

    # Check Overall
    assert "Overall: Refactor common logic." in output_str
    assert "Overall: Adhere to SOLID." in output_str
    assert "Overall: Check inputs." in output_str

    # Check Python file with stubs
    assert "--- File: src/utils.py (python) ---" in output_str
    assert "Impact: Python file modified." in output_str
    assert "Dependency Note: Modified Function `util_func(arg1)`" in output_str
    assert "Testing Suggestion: Modified function `util_func(arg1)` detected." in output_str
    assert "Generated Python Test Stubs:" in output_str
    assert "For new function `new_helper` (in src/utils.py):" in output_str
    assert "Suggested Test File: `tests/test_utils.py`" in output_str
    assert "```python\nimport unittest\n# ... stub for new_helper ...\n```" in output_str
    assert "(Note: These are basic stubs. Please review, adjust paths, and implement test logic.)" in output_str

    # Check Java file
    assert "--- File: com/example/MyClass.java (java) ---" in output_str
    assert "Impact: Java file modified." in output_str
    assert "Dependency Note: Modified public method `getItems(String filter)`" in output_str
    assert "Testing Suggestion: Modified public method `getItems(String filter)`" in output_str
    assert "Linting Issues (java - Checkstyle):" in output_str
    assert "L5:1 [JavadocPackage] Missing package-info.java file. (Severity: info)" in output_str

    # Check POM file
    assert "--- File: pom.xml (maven_pom) ---" in output_str
    assert "Impact: pom.xml was modified." in output_str
    assert "Maven POM Dependency Changes/Observations:" in output_str
    assert "    - Potentially 1 new/modified <dependency> block(s)" in output_str

    # Check Other file
    assert "--- File: README.md (other) ---" in output_str
    assert "Impact: Docs changed." in output_str
    # Ensure no code-specific sections for 'other' (spot check one)
    readme_section_start = output_str.find("--- File: README.md (other) ---")
    readme_section_end = len(output_str) # Assume it's the last
    if readme_section_start != -1:
        readme_suggestions = output_str[readme_section_start:readme_section_end]
        assert "Dependency Note:" not in readme_suggestions


def test_generate_suggestions_other_file_no_impact():
    analysis_results = { 'overall_summary': {}, 'file_specific_findings': [{'file_path': 'data.json', 'language': 'other', 'impacts': []}]}
    suggestions = generate_suggestions(analysis_results)
    json_header = "--- File: data.json (other) ---"; assert json_header in suggestions
    json_idx = suggestions.index(json_header); assert "No specific findings for this file." in suggestions[json_idx + 1]
