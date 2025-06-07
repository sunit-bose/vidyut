import pytest
from src.code_analyzer import analyze_code_changes, _analyze_python_file, _analyze_java_file, _analyze_other_file, RUDIMENTARY_SECURITY_KEYWORDS
from unittest.mock import patch, MagicMock # Ensure MagicMock is imported

@pytest.fixture
def mock_get_content(mocker):
    # Path for mocking where get_file_content_at_ref is looked up by code_analyzer.py
    # This assumes get_file_content_at_ref is imported directly into src.code_analyzer's namespace
    return mocker.patch('src.code_analyzer.get_file_content_at_ref')

def test_analyze_code_changes_empty_pr_data(capsys):
    """Test with empty or invalid pr_data (None or missing 'files_changed')."""
    expected_empty_result = {
        'overall_summary': {
            'reuse_suggestions': [],
            'solid_violations': [],
            'general_security_reminders': []
        },
        'file_specific_findings': []
    }
    result_none = analyze_code_changes(None)
    assert result_none == expected_empty_result
    captured_none = capsys.readouterr()
    assert "Error: Invalid PR data provided for analysis in analyze_code_changes." in captured_none.out

    result_no_files_key = analyze_code_changes({'title': 'Test PR'})
    assert result_no_files_key == expected_empty_result
    captured_no_files_key = capsys.readouterr()
    assert "Error: Invalid PR data provided for analysis in analyze_code_changes." in captured_no_files_key.out


def test_analyze_code_changes_dispatches_correctly(mocker):
    mock_py_analyzer = mocker.patch('src.code_analyzer._analyze_python_file', return_value={'language': 'python', 'file_path': 'test.py', 'impacts':[], 'dependencies':[], 'tests_suggestions':[], 'security_issues':[], 'linting_issues':[]})
    mock_java_analyzer = mocker.patch('src.code_analyzer._analyze_java_file', return_value={'language': 'java', 'file_path': 'Test.java', 'impacts':[], 'dependencies':[], 'tests_suggestions':[], 'security_issues':[], 'linting_issues':[]})
    mock_other_analyzer = mocker.patch('src.code_analyzer._analyze_other_file', return_value={'language': 'other', 'file_path': 'README.md', 'impacts':[], 'dependencies':[], 'tests_suggestions':[], 'security_issues':[], 'linting_issues':[]}) # linting_issues typically not for 'other'

    pr_data_dispatch = {
        'title': 'Test Dispatch', 'owner':'o', 'repo':'r', 'head_sha':'s', # Add owner/repo/sha for content fetching mock
        'files_changed': [
            {'filename': 'test.py', 'status': 'modified', 'patch': '...'},
            {'filename': 'Test.java', 'status': 'added', 'patch': '...'},
            {'filename': 'README.md', 'status': 'modified', 'patch': '...'},
            {'filename': 'another.txt', 'status': 'modified', 'patch': '...'}
        ]
    }
    results = analyze_code_changes(pr_data_dispatch)

    mock_py_analyzer.assert_called_once_with(pr_data_dispatch['files_changed'][0], pr_data_dispatch)
    mock_java_analyzer.assert_called_once_with(pr_data_dispatch['files_changed'][1], pr_data_dispatch)
    assert mock_other_analyzer.call_count == 2
    mock_other_analyzer.assert_any_call(pr_data_dispatch['files_changed'][2], pr_data_dispatch)
    mock_other_analyzer.assert_any_call(pr_data_dispatch['files_changed'][3], pr_data_dispatch)
    assert len(results['file_specific_findings']) == 4

# --- Tests for _analyze_python_file ---

def test_analyze_python_file_with_content_fetches_and_lints(mock_get_content, mocker):
    mock_get_content.return_value = "print('Hello World') # Python content"
    mock_subprocess_run = mocker.patch('subprocess.run')

    mock_flake8_result = MagicMock()
    mock_flake8_result.stdout = "temp.py:1:1: F401 'module' imported but unused"
    mock_flake8_result.stderr = ""
    mock_subprocess_run.return_value = mock_flake8_result

    file_info = {'filename': 'test.py', 'patch': '...'} # Patch might still be used for security scan
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 'sha123'}

    findings = _analyze_python_file(file_info, pr_data)

    mock_get_content.assert_called_once_with('o', 'r', 'test.py', 'sha123', {"Accept": "application/vnd.github.v3+json"})
    mock_subprocess_run.assert_called_once() # Check that flake8 was called
    assert len(findings['linting_issues']) > 0
    assert findings['linting_issues'][0]['code'] == 'F401'
    assert "Python file test.py was modified" in findings['impacts'][0] # Default impact

def test_analyze_python_file_content_fetch_fails(mock_get_content, mocker):
    mock_get_content.return_value = None # Simulate content fetch failure
    mock_subprocess_run = mocker.patch('subprocess.run')

    file_info = {'filename': 'test.py', 'patch': 'some changes'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 'sha123'}

    findings = _analyze_python_file(file_info, pr_data)

    mock_get_content.assert_called_once()
    mock_subprocess_run.assert_not_called() # Flake8 should not be called
    expected_impact_message = "Python file test.py changed, but full content not fetched for Flake8 (using patch for other checks if available)."
    assert expected_impact_message in findings['impacts'] # Check if the message is one of the impacts
    assert findings['linting_issues'] == []
    # Security scan on patch should still run
    assert not findings['security_issues'] # Assuming 'some changes' has no keywords

def test_analyze_python_file_security_keyword_found(mock_get_content): # mock_get_content to simulate no content for Flake8
    mock_get_content.return_value = "print('clean code')" # Assume Flake8 runs on this
    file_info_py_sec = {
        'filename': 'sec.py', 'status': 'modified',
        'patch': '# TODO:SECURITY fix this later'
    }
    original_keywords = RUDIMENTARY_SECURITY_KEYWORDS[:]
    if "TODO:SECURITY" not in RUDIMENTARY_SECURITY_KEYWORDS:
        RUDIMENTARY_SECURITY_KEYWORDS.append("TODO:SECURITY")

    findings = _analyze_python_file(file_info_py_sec, {'owner':'o','repo':'r','head_sha':'s'})

    assert any("Potential security keyword 'TODO:SECURITY' found in changed lines." in issue for issue in findings['security_issues'])
    RUDIMENTARY_SECURITY_KEYWORDS[:] = original_keywords

# --- Tests for _analyze_java_file ---

def test_analyze_java_file_with_content_fetches_and_lints(mock_get_content, mocker):
    mock_get_content.return_value = "public class Test {} // Java content"
    mock_subprocess_run = mocker.patch('subprocess.run')

    mock_checkstyle_result = MagicMock()
    # Simulate Checkstyle XML output for one error
    mock_checkstyle_result.stdout = """<?xml version="1.0" encoding="UTF-8"?>
<checkstyle version="8.0">
<file name="/tmp/tempfile.java">
<error line="1" column="1" severity="error" message="Missing a Javadoc comment." source="com.puppycrawl.tools.checkstyle.checks.javadoc.MissingJavadocTypeCheck"/>
</file>
</checkstyle>"""
    mock_checkstyle_result.stderr = ""
    mock_subprocess_run.return_value = mock_checkstyle_result

    file_info = {'filename': 'Test.java', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 'sha123'}

    findings = _analyze_java_file(file_info, pr_data)

    mock_get_content.assert_called_once_with('o', 'r', 'Test.java', 'sha123', {"Accept": "application/vnd.github.v3+json"})
    mock_subprocess_run.assert_called_once() # Check that Checkstyle was called
    assert len(findings['linting_issues']) > 0
    assert findings['linting_issues'][0]['code'] == 'MissingJavadocTypeCheck'
    assert "Java file Test.java was modified" in findings['impacts'][0]

def test_analyze_java_file_content_fetch_fails(mock_get_content, mocker):
    mock_get_content.return_value = None # Simulate content fetch failure
    mock_subprocess_run = mocker.patch('subprocess.run')

    file_info = {'filename': 'Test.java', 'patch': 'some java changes'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 'sha123'}

    findings = _analyze_java_file(file_info, pr_data)

    mock_get_content.assert_called_once()
    mock_subprocess_run.assert_not_called() # Checkstyle should not be called
    expected_impact_message = "Java file Test.java changed, but full content not fetched for Checkstyle (using patch for other checks if available)."
    assert expected_impact_message in findings['impacts'] # Check if the message is one of the impacts
    assert findings['linting_issues'] == []
    assert not findings['security_issues']

def test_analyze_java_file_security_keyword_found(mock_get_content): # mock_get_content to simulate no content for Checkstyle
    mock_get_content.return_value = "class Clean {}" # Assume Checkstyle runs on this
    file_info_java_sec = {
        'filename': 'App.java', 'status': 'modified',
        'patch': '// FIXME:SECURITY this is not safe'
    }
    original_keywords = RUDIMENTARY_SECURITY_KEYWORDS[:]
    if "FIXME:SECURITY" not in RUDIMENTARY_SECURITY_KEYWORDS:
        RUDIMENTARY_SECURITY_KEYWORDS.append("FIXME:SECURITY")

    findings = _analyze_java_file(file_info_java_sec, {'owner':'o','repo':'r','head_sha':'s'})

    assert any("Potential security keyword 'FIXME:SECURITY' found in changed lines." in issue for issue in findings['security_issues'])
    RUDIMENTARY_SECURITY_KEYWORDS[:] = original_keywords

# --- Test for _analyze_other_file (remains unchanged but good to keep) ---
def test_analyze_other_file():
    file_info_other = {'filename': 'README.md', 'status': 'modified', 'patch': 'Some changes.'}
    findings = _analyze_other_file(file_info_other, {}) # pr_data not used by _analyze_other_file
    assert "Non-code file changed: README.md" in findings['impacts'][0]
    assert not findings.get('linting_issues') # Should not have linting_issues key or it's empty
    assert not findings['security_issues']
    assert not findings['dependencies']
