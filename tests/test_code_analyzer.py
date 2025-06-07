import pytest
from src.code_analyzer import analyze_code_changes, _analyze_python_file, _analyze_java_file, _analyze_other_file, RUDIMENTARY_SECURITY_KEYWORDS
from unittest.mock import patch # If not already imported

# Previous tests for analyze_code_changes (before multi-language dispatch)
# might need to be adapted or removed if they are no longer relevant
# or if their tested functionality is now within the _analyze_xxx_file functions.
# For this update, we're focusing on adding new tests for the new structure.

def test_analyze_code_changes_empty_pr_data(capsys):
    """Test with empty or invalid pr_data (None or missing 'files_changed')."""
    # This test is still relevant as it checks the initial guard clause.
    expected_empty_result = {
        'overall_summary': {
            'reuse_suggestions': [],
            'solid_violations': [],
            'general_security_reminders': []
        },
        'file_specific_findings': []
    }

    # Test with None pr_data
    result_none = analyze_code_changes(None)
    assert result_none == expected_empty_result
    captured_none = capsys.readouterr()
    assert "Error: Invalid PR data provided for analysis in analyze_code_changes." in captured_none.out

    # Test with pr_data missing 'files_changed' key
    result_no_files_key = analyze_code_changes({'title': 'Test PR'})
    assert result_no_files_key == expected_empty_result
    captured_no_files_key = capsys.readouterr()
    assert "Error: Invalid PR data provided for analysis in analyze_code_changes." in captured_no_files_key.out


def test_analyze_code_changes_dispatches_correctly(mocker):
    # Mock the individual file analyzers
    mock_py_analyzer = mocker.patch('src.code_analyzer._analyze_python_file', return_value={'language': 'python', 'file_path': 'test.py', 'impacts':[], 'dependencies':[], 'tests_suggestions':[], 'security_issues':[]})
    mock_java_analyzer = mocker.patch('src.code_analyzer._analyze_java_file', return_value={'language': 'java', 'file_path': 'Test.java', 'impacts':[], 'dependencies':[], 'tests_suggestions':[], 'security_issues':[]})
    mock_other_analyzer = mocker.patch('src.code_analyzer._analyze_other_file', return_value={'language': 'other', 'file_path': 'README.md', 'impacts':[], 'dependencies':[], 'tests_suggestions':[], 'security_issues':[]})

    pr_data_dispatch = {
        'title': 'Test Dispatch',
        'files_changed': [
            {'filename': 'test.py', 'status': 'modified', 'patch': '...'},
            {'filename': 'Test.java', 'status': 'added', 'patch': '...'},
            {'filename': 'README.md', 'status': 'modified', 'patch': '...'},
            {'filename': 'another.txt', 'status': 'modified', 'patch': '...'} # Will also go to _analyze_other_file
        ]
    }
    results = analyze_code_changes(pr_data_dispatch)

    mock_py_analyzer.assert_called_once_with(pr_data_dispatch['files_changed'][0], pr_data_dispatch)
    mock_java_analyzer.assert_called_once_with(pr_data_dispatch['files_changed'][1], pr_data_dispatch)

    assert mock_other_analyzer.call_count == 2
    # Check that the calls were made with the correct arguments for 'other' files
    mock_other_analyzer.assert_any_call(pr_data_dispatch['files_changed'][2], pr_data_dispatch)
    mock_other_analyzer.assert_any_call(pr_data_dispatch['files_changed'][3], pr_data_dispatch)

    assert len(results['file_specific_findings']) == 4
    assert results['file_specific_findings'][0]['language'] == 'python'
    assert results['file_specific_findings'][1]['language'] == 'java'
    assert results['file_specific_findings'][2]['language'] == 'other'
    assert results['file_specific_findings'][3]['language'] == 'other' # For another.txt

# --- Tests for _analyze_python_file ---
def test_analyze_python_file_security_keyword_found():
    file_info_py_sec = {
        'filename': 'sec.py', 'status': 'modified',
        'patch': 'some python code\n# TODO:SECURITY fix this later\nprint("hello")'
    }
    # Ensure the specific keyword is in the list for this test
    # This approach of modifying global list is okay for testing if restored,
    # but for more complex scenarios, dependency injection or patching the list itself might be better.
    original_keywords = RUDIMENTARY_SECURITY_KEYWORDS[:] # Shallow copy for restoration
    if "TODO:SECURITY" not in RUDIMENTARY_SECURITY_KEYWORDS:
        RUDIMENTARY_SECURITY_KEYWORDS.append("TODO:SECURITY")

    findings = _analyze_python_file(file_info_py_sec, {}) # pr_data is not deeply used by current version of _analyze_python_file

    assert any("Potential security keyword 'TODO:SECURITY' found" in issue for issue in findings['security_issues'])
    assert "Changes detected in sec.py" in findings['tests_suggestions'][0] # Check other suggestions

    RUDIMENTARY_SECURITY_KEYWORDS[:] = original_keywords # Restore

def test_analyze_python_file_no_security_keyword():
    file_info_py_clean = {'filename': 'clean.py', 'status': 'modified', 'patch': 'print("all good")'}
    findings = _analyze_python_file(file_info_py_clean, {})
    assert not findings['security_issues'] # Should be empty
    assert "Changes detected in clean.py" in findings['tests_suggestions'][0]

def test_analyze_python_file_no_patch():
    file_info_no_patch = {'filename': 'no_patch.py', 'status': 'modified', 'patch': None}
    findings = _analyze_python_file(file_info_no_patch, {})
    assert "no patch data available" in findings['impacts'][0]
    assert not findings['security_issues']
    assert "Consider adding/updating unit tests for changes in no_patch.py" in findings['tests_suggestions'][0]

# --- Tests for _analyze_java_file ---
def test_analyze_java_file_security_keyword_found():
    file_info_java_sec = {
        'filename': 'App.java', 'status': 'modified',
        'patch': '// FIXME:SECURITY this is not safe\nString pass = "hardcoded_password";'
    }
    original_keywords = RUDIMENTARY_SECURITY_KEYWORDS[:]
    # Ensure necessary keywords for the test are present
    test_keywords_to_ensure = ["FIXME:SECURITY", "hardcoded_password"]
    for kw in test_keywords_to_ensure:
        if kw not in RUDIMENTARY_SECURITY_KEYWORDS:
            RUDIMENTARY_SECURITY_KEYWORDS.append(kw)

    findings = _analyze_java_file(file_info_java_sec, {})

    assert any("Potential security keyword 'FIXME:SECURITY' found" in issue for issue in findings['security_issues'])
    assert any("Potential security keyword 'hardcoded_password' found" in issue for issue in findings['security_issues'])
    assert "Review changes in App.java" in findings['tests_suggestions'][0]

    RUDIMENTARY_SECURITY_KEYWORDS[:] = original_keywords # Restore

def test_analyze_java_file_no_security_keyword():
    file_info_java_clean = {'filename': 'Clean.java', 'status': 'modified', 'patch': 'System.out.println("all good");'}
    findings = _analyze_java_file(file_info_java_clean, {})
    assert not findings['security_issues']
    assert "Review changes in Clean.java" in findings['tests_suggestions'][0]

def test_analyze_java_file_no_patch():
    file_info_no_patch_java = {'filename': 'NoPatch.java', 'status': 'modified', 'patch': None}
    findings = _analyze_java_file(file_info_no_patch_java, {})
    assert "no patch data available" in findings['impacts'][0]
    assert not findings['security_issues']
    assert "Generic reminder: Ensure adequate JUnit test coverage for NoPatch.java" in findings['tests_suggestions'][0]

# --- Test for _analyze_other_file ---
def test_analyze_other_file():
    file_info_other = {'filename': 'README.md', 'status': 'modified', 'patch': 'Some changes.'}
    findings = _analyze_other_file(file_info_other, {})
    assert "Non-code file changed: README.md" in findings['impacts'][0]
    assert not findings['tests_suggestions'] # Should be empty as per current _analyze_other_file
    assert not findings['security_issues'] # No security scan for 'other' by default
    assert not findings['dependencies']

# Old tests like test_analyze_code_changes_no_files_changed,
# test_analyze_code_changes_with_one_file_changed etc. might need review.
# The main `analyze_code_changes` function's responsibility is now more about dispatch
# and overall summary, less about direct impact area formatting from patches.
# The overall_summary part of `analyze_code_changes` can be tested separately if it grows complex.
# For now, the dispatch test covers the main new structural aspect.
# The `test_analyze_code_changes_empty_pr_data` is still very relevant.
