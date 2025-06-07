import pytest
from src.code_analyzer import analyze_code_changes, _analyze_python_file, _analyze_java_file, _analyze_other_file, RUDIMENTARY_SECURITY_KEYWORDS
from unittest.mock import patch, MagicMock # Ensure MagicMock is imported

@pytest.fixture
def mock_get_content(mocker):
    return mocker.patch('src.code_analyzer.get_file_content_at_ref')

# --- Existing tests for analyze_code_changes (dispatch and empty data) ---
def test_analyze_code_changes_empty_pr_data(capsys):
    expected_empty_result = {
        'overall_summary': {
            'reuse_suggestions': [], 'solid_violations': [], 'general_security_reminders': []
        }, 'file_specific_findings': []
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
    mock_py_analyzer = mocker.patch('src.code_analyzer._analyze_python_file', return_value={'language': 'python', 'file_path': 'test.py', 'impacts':[], 'dependencies':[], 'tests_suggestions':[], 'security_issues':[], 'linting_issues':[], 'python_definitions':[]})
    mock_java_analyzer = mocker.patch('src.code_analyzer._analyze_java_file', return_value={'language': 'java', 'file_path': 'Test.java', 'impacts':[], 'dependencies':[], 'tests_suggestions':[], 'security_issues':[], 'linting_issues':[]})
    mock_other_analyzer = mocker.patch('src.code_analyzer._analyze_other_file', return_value={'language': 'other', 'file_path': 'README.md', 'impacts':[], 'dependencies':[], 'tests_suggestions':[], 'security_issues':[], 'linting_issues':[]})

    pr_data_dispatch = {
        'title': 'Test Dispatch', 'owner':'o', 'repo':'r', 'head_sha':'s',
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

# --- New and Updated Tests for _analyze_python_file ---

SAMPLE_PYTHON_CODE_SIMPLE_FUNC = """
def hello(name):
    print(f"Hello, {name}")
"""

SAMPLE_PYTHON_CODE_CLASS_METHOD = """
class Greeter:
    def __init__(self, greeting="Hello"):
        self.greeting = greeting

    def greet(self, name):
        return f"{self.greeting}, {name}!"

def standalone_func():
    pass
"""

SAMPLE_PYTHON_CODE_WITH_DECORATORS_AND_BASES = """
@my_decorator
@another_decorator(arg=1)
class MyClass(Base1, Base2):
    @classmethod
    def factory(cls, value):
        return cls(value)

    def __init__(self, value):
        self.value = value
"""

def test_analyze_python_file_ast_parsing_extraction(mock_get_content):
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_CLASS_METHOD
    file_info_new = {'filename': 'greeter.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info_new, pr_data)

    assert 'python_definitions' in findings
    defs = findings['python_definitions']
    assert len(defs) == 4

    class_def = next((d for d in defs if d['name'] == 'Greeter' and d['type'] == 'class'), None)
    init_method = next((d for d in defs if d['name'] == '__init__' and d['type'] == 'method'), None)
    greet_method = next((d for d in defs if d['name'] == 'greet' and d['type'] == 'method'), None)
    standalone_func_def = next((d for d in defs if d['name'] == 'standalone_func' and d['type'] == 'function'), None)

    assert class_def is not None
    assert class_def['start_line'] == 2
    assert class_def['change_type'] == 'new'

    assert init_method is not None
    assert init_method['args'] == ['self', 'greeting']
    assert init_method['start_line'] == 3
    assert init_method['change_type'] == 'new'

    assert greet_method is not None
    assert greet_method['args'] == ['self', 'name']
    assert greet_method['start_line'] == 6
    assert greet_method['change_type'] == 'new'

    assert standalone_func_def is not None
    assert standalone_func_def['args'] == []
    assert standalone_func_def['start_line'] == 9
    assert standalone_func_def['change_type'] == 'new'

def test_analyze_python_file_identify_modified_definition(mock_get_content):
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_SIMPLE_FUNC
    patch_text = "@@ -1,2 +2,2 @@\n-def hello(old_name):\n-    print(f\"Hi, {old_name}\")\n+def hello(name):\n+    print(f\"Hello, {name}\")"
    file_info = {'filename': 'hello.py', 'status': 'modified', 'patch': patch_text}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)

    assert 'python_definitions' in findings
    defs = findings['python_definitions']
    assert len(defs) == 1
    hello_func = defs[0]
    assert hello_func['name'] == 'hello'
    assert hello_func['change_type'] == 'modified'
    assert hello_func['start_line'] == 2

def test_analyze_python_file_definition_not_in_patch(mock_get_content):
    code = "\n".join([
        "def func_one(): # line 1",
        "    pass",       # line 2
        "def func_two(): # line 3",
        "    pass"        # line 4
    ])
    mock_get_content.return_value = code
    patch_text = "@@ -1,2 +1,2 @@\n-def func_one():\n-    pass\n+def func_one():\n+    print('changed')"
    file_info = {'filename': 'test.py', 'status': 'modified', 'patch': patch_text}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)

    assert 'python_definitions' in findings
    defs = findings['python_definitions']
    assert len(defs) == 1
    assert defs[0]['name'] == 'func_one'
    assert defs[0]['change_type'] == 'modified'

def test_analyze_python_file_specific_dependency_notes(mock_get_content):
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_SIMPLE_FUNC
    file_info = {'filename': 'hello.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)

    assert 'dependencies' in findings
    assert len(findings['dependencies']) == 1
    assert "New Function `hello(name)`" in findings['dependencies'][0] # Corrected 'Function'
    assert "in hello.py. Review its usage" in findings['dependencies'][0]

def test_analyze_python_file_specific_test_suggestions(mock_get_content):
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_CLASS_METHOD
    file_info = {'filename': 'greeter.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)

    assert 'tests_suggestions' in findings
    assert len(findings['tests_suggestions']) == 4
    assert any("New class `Greeter`" in sugg for sugg in findings['tests_suggestions'])
    assert any("New method `__init__(self, greeting)`" in sugg for sugg in findings['tests_suggestions'])
    assert any("New method `greet(self, name)`" in sugg for sugg in findings['tests_suggestions'])
    assert any("New function `standalone_func()`" in sugg for sugg in findings['tests_suggestions'])

def test_analyze_python_file_fallback_test_suggestion(mock_get_content):
    mock_get_content.return_value = "print('just some script code')" # No defs
    patch_text = "@@ -1,0 +1,1 @@\n+print('just some script code')" # This will create changed_line_info
    file_info = {'filename': 'script.py', 'status': 'added', 'patch': patch_text}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)

    assert not findings['python_definitions']
    assert len(findings['tests_suggestions']) >= 1
    # Because patch_text creates changed_line_info, the first fallback condition is met
    expected_suggestion = "Changes detected in script.py (hunks: 1). Consider specific unit tests for modified logic based on patch."
    assert any(expected_suggestion in sugg for sugg in findings['tests_suggestions'])

def test_analyze_python_file_decorators_and_bases(mock_get_content):
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_WITH_DECORATORS_AND_BASES
    file_info = {'filename': 'complex.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)
    defs = findings['python_definitions']

    my_class_def = next((d for d in defs if d['name'] == 'MyClass'), None)
    assert my_class_def is not None
    assert 'my_decorator' in my_class_def['decorators']
    assert any("Call(func=Name(id='another_decorator'" in dec_dump for dec_dump in my_class_def['decorators'] if isinstance(dec_dump, str) and "another_decorator" in dec_dump)
    assert my_class_def['bases'] == ['Base1', 'Base2']

    factory_method = next((d for d in defs if d['name'] == 'factory'), None)
    assert factory_method is not None
    assert 'classmethod' in factory_method['decorators']

def test_analyze_python_file_with_content_fetches_and_lints(mock_get_content, mocker):
    mock_get_content.return_value = "import os\nprint(os.listdir())"
    mock_subprocess_run = mocker.patch('subprocess.run')
    mock_flake8_result = MagicMock()
    mock_flake8_result.stdout = "temp.py:1:1: F401 'os' imported but unused"
    mock_flake8_result.stderr = ""
    mock_subprocess_run.return_value = mock_flake8_result
    file_info = {'filename': 'test.py', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 'sha123'}
    findings = _analyze_python_file(file_info, pr_data)
    mock_get_content.assert_called_once_with('o', 'r', 'test.py', 'sha123', {"Accept": "application/vnd.github.v3+json"})
    mock_subprocess_run.assert_called_once()
    assert len(findings['linting_issues']) > 0
    assert findings['linting_issues'][0]['code'] == 'F401'

def test_analyze_python_file_content_fetch_fails(mock_get_content, mocker):
    mock_get_content.return_value = None
    mock_subprocess_run = mocker.patch('subprocess.run')
    file_info = {'filename': 'test.py', 'patch': 'some changes'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 'sha123'}
    findings = _analyze_python_file(file_info, pr_data)
    mock_get_content.assert_called_once()
    mock_subprocess_run.assert_not_called()
    assert any("full content not fetched for AST parsing and Flake8 analysis" in imp for imp in findings['impacts'])
    assert findings['linting_issues'] == []
    assert not findings['security_issues']

def test_analyze_python_file_security_keyword_found(mock_get_content):
    mock_get_content.return_value = "print('clean code')"
    file_info_py_sec = {
        'filename': 'sec.py', 'status': 'modified',
        'patch': '# TODO:SECURITY fix this later'
    }
    original_keywords = RUDIMENTARY_SECURITY_KEYWORDS[:]
    if "TODO:SECURITY" not in RUDIMENTARY_SECURITY_KEYWORDS:
        RUDIMENTARY_SECURITY_KEYWORDS.append("TODO:SECURITY")
    findings = _analyze_python_file(file_info_py_sec, {'owner':'o','repo':'r','head_sha':'s'})
    # Corrected expected message to include "(patch scan)"
    assert any("Potential security keyword 'TODO:SECURITY' found in changed lines (patch scan)." in issue for issue in findings['security_issues'])
    RUDIMENTARY_SECURITY_KEYWORDS[:] = original_keywords

def test_analyze_java_file_with_content_fetches_and_lints(mock_get_content, mocker):
    mock_get_content.return_value = "public class Test {} // Java content"
    mock_subprocess_run = mocker.patch('subprocess.run')
    mock_checkstyle_result = MagicMock()
    mock_checkstyle_result.stdout = """<?xml version="1.0" encoding="UTF-8"?>
<checkstyle version="8.0"><file name="/tmp/tempfile.java">
<error line="1" column="1" severity="error" message="Missing a Javadoc comment." source="com.puppycrawl.tools.checkstyle.checks.javadoc.MissingJavadocTypeCheck"/>
</file></checkstyle>"""
    mock_checkstyle_result.stderr = ""
    mock_subprocess_run.return_value = mock_checkstyle_result
    file_info = {'filename': 'Test.java', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 'sha123'}
    findings = _analyze_java_file(file_info, pr_data)
    mock_get_content.assert_called_once_with('o', 'r', 'Test.java', 'sha123', {"Accept": "application/vnd.github.v3+json"})
    mock_subprocess_run.assert_called_once()
    assert len(findings['linting_issues']) > 0
    assert findings['linting_issues'][0]['code'] == 'MissingJavadocTypeCheck'

def test_analyze_java_file_content_fetch_fails(mock_get_content, mocker):
    mock_get_content.return_value = None
    mock_subprocess_run = mocker.patch('subprocess.run')
    file_info = {'filename': 'Test.java', 'patch': 'some java changes'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 'sha123'}
    findings = _analyze_java_file(file_info, pr_data)
    mock_get_content.assert_called_once()
    mock_subprocess_run.assert_not_called()
    assert any("full content not fetched for Checkstyle" in imp for imp in findings['impacts'])
    assert findings['linting_issues'] == []
    assert not findings['security_issues']

def test_analyze_java_file_security_keyword_found(mock_get_content):
    mock_get_content.return_value = "class Clean {}"
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

def test_analyze_other_file():
    file_info_other = {'filename': 'README.md', 'status': 'modified', 'patch': 'Some changes.'}
    findings = _analyze_other_file(file_info_other, {})
    assert "Non-code file changed: README.md" in findings['impacts'][0]
    assert not findings.get('linting_issues') or findings.get('linting_issues') == []
    assert not findings['security_issues']
    assert not findings['dependencies']
