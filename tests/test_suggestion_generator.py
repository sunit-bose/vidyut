import pytest # Ensure pytest is imported if not already
from src.suggestion_generator import generate_suggestions

# Test with None input (already good)
def test_generate_suggestions_input_none(capsys):
    """Test with None as analysis_results."""
    result_none = generate_suggestions(None)
    assert result_none == []
    captured_none = capsys.readouterr()
    assert "Error: No analysis results provided for suggestion generation." in captured_none.out

# Test with completely empty analysis results (overall_summary and file_specific_findings are empty)
def test_generate_suggestions_completely_empty_analysis():
    analysis_results = {
        'overall_summary': {
            'reuse_suggestions': [],
            'solid_violations': [],
            'general_security_reminders': []
        },
        'file_specific_findings': []
    }
    result = generate_suggestions(analysis_results)
    # Expect the "No specific suggestions..." message because both overall and file-specific are empty.
    assert result == ["No specific suggestions based on the current analysis. General best practices still apply."]

# Test with only overall summary findings, no file-specific findings
def test_generate_suggestions_only_overall_summary():
    analysis_results = {
        'overall_summary': {
            'reuse_suggestions': ['Overall: Consider abstracting common utilities.'],
            'solid_violations': ['Overall: Check for SRP violations.'],
            'general_security_reminders': ['Overall: Remember to validate all inputs.']
        },
        'file_specific_findings': [] # No file-specific details
    }
    result = generate_suggestions(analysis_results)
    assert "Overall Code Reuse: Consider abstracting common utilities." in result
    assert "Overall Design Pattern: Check for SRP violations." in result
    assert "Overall: Remember to validate all inputs." in result
    # Since file_specific_findings is empty, and suggestions list is populated by overall,
    # it should not return "No specific suggestions..."
    assert len(result) == 3


def test_generate_suggestions_with_new_structure_and_security():
    """
    Tests the suggestion generator with the multi-language structure,
    including conditional display of sections and security issues.
    """
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
                'security_issues': ["Potential security keyword 'HARDCODED_PASSWORD' found in changes."]
            },
            {
                'file_path': 'com/myapp/Main.java', 'language': 'java',
                'impacts': ['Java file com/myapp/Main.java was added.'],
                'dependencies': [], # Test empty list for conditional output
                'tests_suggestions': ['Testing: Ensure JUnit tests cover `Main.java`.'],
                'security_issues': [] # Test empty list
            },
            {
                'file_path': 'docs/guide.md', 'language': 'other',
                'impacts': ['Documentation file docs/guide.md was updated.'],
                # For 'other' files, dependencies, tests_suggestions, security_issues are usually not populated
                # by the current analyzer logic, so they should not appear in suggestions.
            },
            {
                'file_path': 'src/another.py', 'language': 'python',
                'impacts': ['Python file src/another.py had minor changes.'],
                'dependencies': [],
                'tests_suggestions': [],
                'security_issues': []
                # This will test the "No further specific code analysis suggestions..." message
            }
        ]
    }

    suggestions = generate_suggestions(mock_analysis)

    # Verify Overall Suggestions
    assert "Overall Code Reuse: Abstract common patterns." in suggestions
    assert "Overall Design Pattern: Review Liskov Substitution Principle." in suggestions
    assert "Overall: Sanitize external data." in suggestions

    # Verify Python File (src/utils.py)
    # Find the start of this file's suggestions
    py_utils_header = "--- File: src/utils.py (python) ---"
    assert py_utils_header in suggestions
    py_utils_idx = suggestions.index(py_utils_header)

    assert "Impact: Python file src/utils.py was modified significantly." in suggestions[py_utils_idx + 1]
    assert "Dependency Note: Dependency: `helper_func` might be affected." in suggestions[py_utils_idx + 2]
    assert "Testing Suggestion: Testing: Add unit tests for new logic in `utils.py`." in suggestions[py_utils_idx + 3]
    assert "Security Concern: Potential security keyword 'HARDCODED_PASSWORD' found in changes." in suggestions[py_utils_idx + 4]

    # Verify Java File (com/myapp/Main.java)
    java_main_header = "--- File: com/myapp/Main.java (java) ---"
    assert java_main_header in suggestions
    java_main_idx = suggestions.index(java_main_header)

    assert "Impact: Java file com/myapp/Main.java was added." in suggestions[java_main_idx + 1]
    # Check that "Dependency Note" is NOT present for Main.java as its 'dependencies' list was empty
    # This requires checking the slice of suggestions relevant to Main.java
    # Find next header or end of list to define the slice
    next_header_idx_after_java = len(suggestions) # Default to end of list
    for i in range(java_main_idx + 1, len(suggestions)):
        if suggestions[i].startswith("--- File:"):
            next_header_idx_after_java = i
            break
    java_file_suggestions_slice = suggestions[java_main_idx + 1 : next_header_idx_after_java]
    assert not any("Dependency Note:" in s for s in java_file_suggestions_slice)
    assert any("Testing Suggestion: Ensure JUnit tests cover `Main.java`." in s for s in java_file_suggestions_slice)
    assert not any("Security Concern:" in s for s in java_file_suggestions_slice) # security_issues was empty

    # Verify Other File (docs/guide.md)
    md_guide_header = "--- File: docs/guide.md (other) ---"
    assert md_guide_header in suggestions
    md_guide_idx = suggestions.index(md_guide_header)

    assert "Impact: Documentation file docs/guide.md was updated." in suggestions[md_guide_idx + 1]
    next_header_idx_after_md = len(suggestions)
    for i in range(md_guide_idx + 1, len(suggestions)):
        if suggestions[i].startswith("--- File:"):
            next_header_idx_after_md = i
            break
    md_file_suggestions_slice = suggestions[md_guide_idx + 1 : next_header_idx_after_md]
    assert not any("Dependency Note:" in s for s in md_file_suggestions_slice)
    assert not any("Testing Suggestion:" in s for s in md_file_suggestions_slice)
    assert not any("Security Concern:" in s for s in md_file_suggestions_slice)

    # Verify Python File (src/another.py) - expecting "No further specific..."
    py_another_header = "--- File: src/another.py (python) ---"
    assert py_another_header in suggestions
    py_another_idx = suggestions.index(py_another_header)

    assert "Impact: Python file src/another.py had minor changes." in suggestions[py_another_idx + 1]
    assert "No further specific code analysis suggestions for this python file in this phase." in suggestions[py_another_idx + 2]


def test_generate_suggestions_other_file_no_impact():
    """Test 'other' file type when it has no impact recorded (should be unusual)."""
    analysis_results = {
        'overall_summary': {},
        'file_specific_findings': [
            {
                'file_path': 'data.json', 'language': 'other',
                'impacts': [], # No impacts
                'dependencies': [], 'tests_suggestions': [], 'security_issues': []
            }
        ]
    }
    suggestions = generate_suggestions(analysis_results)
    json_header = "--- File: data.json (other) ---"
    assert json_header in suggestions
    json_idx = suggestions.index(json_header)
    assert "No specific findings for this file." in suggestions[json_idx + 1]

# Old tests like test_generate_suggestions_with_impact_areas_only etc.
# should be reviewed. The new test_generate_suggestions_with_new_structure_and_security
# covers most cases. test_generate_suggestions_completely_empty_analysis and
# test_generate_suggestions_only_overall_summary are good to keep as they test specific states.
# The old test_generate_suggestions_no_findings is similar to _completely_empty_analysis.
# For this update, the provided tests are comprehensive for the new structure.Okay, `tests/test_suggestion_generator.py` has been successfully updated.

Key changes include:
*   The main test, `test_generate_suggestions_with_new_structure_and_security`, now uses a `mock_analysis` that reflects the detailed multi-language structure from `code_analyzer.py`.
    *   It checks for overall summary suggestions.
    *   It verifies that file-specific sections (impacts, dependencies, test suggestions, security concerns) are correctly generated and included for Python files.
    *   It checks that for Java files, empty lists for dependencies or security issues result in those sections *not* being printed.
    *   It ensures that for 'other' file types, only relevant information (like impacts) is shown, and code-specific sections are omitted.
    *   It also tests the "No further specific code analysis suggestions..." message for code files that have impacts but no other findings.
*   `test_generate_suggestions_completely_empty_analysis` is updated to reflect the new expected output when both overall and file-specific findings are empty.
*   `test_generate_suggestions_only_overall_summary` is kept to test the case where only overall suggestions are present.
*   A new test `test_generate_suggestions_other_file_no_impact` was added to check the specific message for 'other' files when no impacts are listed.
*   The `test_generate_suggestions_input_none` remains unchanged as its logic is still valid.

These tests provide good coverage for the new output formatting and conditional logic in `generate_suggestions` based on the multi-language analysis results and the presence of different types of findings.

Both `tests/test_code_analyzer.py` and `tests/test_suggestion_generator.py` have been updated according to the subtask.

I will now submit the report.
