import pytest
from src.code_analyzer import analyze_code_changes, _analyze_python_file, _analyze_java_file, _analyze_other_file, RUDIMENTARY_SECURITY_KEYWORDS
from unittest.mock import patch, MagicMock

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

# --- Python Analysis Tests ---
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
    assert class_def is not None; assert init_method is not None; assert greet_method is not None; assert standalone_func_def is not None

def test_analyze_python_file_identify_modified_definition(mock_get_content):
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_SIMPLE_FUNC
    patch_text = "@@ -1,2 +2,2 @@\n-def hello(old_name):\n-    print(f\"Hi, {old_name}\")\n+def hello(name):\n+    print(f\"Hello, {name}\")"
    file_info = {'filename': 'hello.py', 'status': 'modified', 'patch': patch_text}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)
    assert 'python_definitions' in findings; defs = findings['python_definitions']
    assert len(defs) == 1; hello_func = defs[0]
    assert hello_func['name'] == 'hello'; assert hello_func['change_type'] == 'modified'

def test_analyze_python_file_definition_not_in_patch(mock_get_content):
    code = "def func_one(): pass\ndef func_two(): pass" # Simplified
    mock_get_content.return_value = code
    patch_text = "@@ -1,1 +1,1 @@\n-def func_one(): pass\n+def func_one(): print('changed')"
    file_info = {'filename': 'test.py', 'status': 'modified', 'patch': patch_text}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)
    assert len(findings['python_definitions']) == 1
    assert findings['python_definitions'][0]['name'] == 'func_one'

def test_analyze_python_file_specific_dependency_notes(mock_get_content):
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_SIMPLE_FUNC
    file_info = {'filename': 'hello.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)
    assert 'dependencies' in findings; assert len(findings['dependencies']) == 1
    assert "New Function `hello(name)` (lines 2-3) in hello.py." in findings['dependencies'][0]

def test_analyze_python_file_specific_test_suggestions(mock_get_content):
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_CLASS_METHOD
    file_info = {'filename': 'greeter.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)
    assert 'tests_suggestions' in findings; assert len(findings['tests_suggestions']) == 4

def test_analyze_python_file_fallback_test_suggestion(mock_get_content):
    mock_get_content.return_value = "print('just some script code')"
    patch_text = "@@ -1,0 +1,1 @@\n+print('just some script code')"
    file_info = {'filename': 'script.py', 'status': 'added', 'patch': patch_text}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)
    assert not findings['python_definitions']
    expected_suggestion = "Changes detected in script.py (hunks: 1). Consider specific unit tests for modified logic based on patch."
    assert any(expected_suggestion in sugg for sugg in findings['tests_suggestions'])

def test_analyze_python_file_decorators_and_bases(mock_get_content):
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_WITH_DECORATORS_AND_BASES
    file_info = {'filename': 'complex.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data)
    defs = findings['python_definitions']
    my_class_def = next((d for d in defs if d['name'] == 'MyClass'), None)
    assert my_class_def is not None; assert 'my_decorator' in my_class_def['decorators']
    assert any("Call(func=Name(id='another_decorator'" in dec for dec in my_class_def['decorators'] if isinstance(dec, str))
    assert my_class_def['bases'] == ['Base1', 'Base2']
    factory_method = next((d for d in defs if d['name'] == 'factory'), None)
    assert factory_method is not None; assert 'classmethod' in factory_method['decorators']

def test_analyze_python_file_with_content_fetches_and_lints(mock_get_content, mocker):
    mock_get_content.return_value = "import os\nprint(os.listdir())"
    mock_subprocess_run = mocker.patch('subprocess.run')
    mock_flake8_result = MagicMock(); mock_flake8_result.stdout = "temp.py:1:1: F401 'os' imported but unused"; mock_flake8_result.stderr = ""
    mock_subprocess_run.return_value = mock_flake8_result
    findings = _analyze_python_file({'filename': 'test.py', 'patch': '...'}, {'owner': 'o', 'repo': 'r', 'head_sha': 's'})
    mock_get_content.assert_called_once(); mock_subprocess_run.assert_called_once()
    assert len(findings['linting_issues']) > 0; assert findings['linting_issues'][0]['code'] == 'F401'

def test_analyze_python_file_content_fetch_fails(mock_get_content, mocker):
    mock_get_content.return_value = None
    mocker.patch('subprocess.run').assert_not_called()
    findings = _analyze_python_file({'filename': 'test.py', 'patch': '...'}, {'owner': 'o', 'repo': 'r', 'head_sha': 's'})
    assert any("full content not fetched" in imp for imp in findings['impacts'])

def test_analyze_python_file_security_keyword_found(mock_get_content):
    mock_get_content.return_value = "print('clean code')"
    file_info = {'filename': 'sec.py', 'status': 'modified', 'patch': '# TODO:SECURITY fix this later'}
    findings = _analyze_python_file(file_info, {'owner':'o','repo':'r','head_sha':'s'})
    assert any("Potential security keyword 'TODO:SECURITY' found in changed lines (patch scan)." in issue for issue in findings['security_issues'])

# --- Java Analysis Tests ---
VIOLATIONS_FILE_CONTENT = """// Intentionally violates Google Java Style for testing Checkstyle
package com.example;
import java.util.List;
import java.util.ArrayList;
public class incorrectClassName {
    public int PublicField = 10;
    private int my_value;
    public void MyMethod() {
        int A = 5 + 3;
        System.out.println("This line is deliberately made very very very very very very very very very very very very very very very very very long to exceed the line length limit.");
        if (A > 0) { System.out.println("Positive"); }
        int magicNumber = 123;
    }
    public void anotherMethod(String BadName) {}
    private void unUsedPrivateMethod() {}
}"""

CLEAN_FILE_CONTENT = """package com.example;
import java.util.ArrayList;
import java.util.List;
public class CheckstyleClean {
    private static final int DEFAULT_CAPACITY = 10;
    private String message;
    private final List<String> items;
    public CheckstyleClean(String initialMessage) {
        this.message = initialMessage;
        this.items = new ArrayList<>(DEFAULT_CAPACITY);
    }
    public String getMessage() { return message; }
    public void setMessage(String newMessage) { this.message = newMessage; }
    public void addItem(String item) { if (item != null && !item.isEmpty()) { this.items.add(item); } }
    public static void main(String[] args) {
        CheckstyleClean clean = new CheckstyleClean("Hello Checkstyle!");
        clean.addItem("Item 1");
        System.out.println(clean.getMessage());
    }
}"""

MOCK_CHECKSTYLE_XML_VIOLATIONS = '''<?xml version="1.0" encoding="UTF-8"?>
<checkstyle version="8.41.1">
<file name="temporary_file.java">
    <error line="5" column="14" severity="error" message="Name &apos;incorrectClassName&apos; must match pattern &apos;^[A-Z][a-zA-Z0-9]*$&apos;." source="com.puppycrawl.tools.checkstyle.checks.naming.TypeNameCheck"/>
    <error line="7" column="17" severity="error" message="Name &apos;PublicField&apos; must match pattern &apos;^[a-z]([a-zA-Z0-9_]*[a-zA-Z0-9])?$&apos;." source="com.puppycrawl.tools.checkstyle.checks.naming.MemberNameCheck"/>
    <error line="10" column="17" severity="error" message="Method name &apos;MyMethod&apos; must match pattern &apos;^[a-z][a-zA-Z0-9]*$&apos;." source="com.puppycrawl.tools.checkstyle.checks.naming.MethodNameCheck"/>
    <error line="12" column="13" severity="error" message="Local variable name &apos;A&apos; must match pattern &apos;^[a-z][a-zA-Z0-9]*$&apos;." source="com.puppycrawl.tools.checkstyle.checks.naming.LocalVariableNameCheck"/>
    <error line="13" severity="error" message="Line is longer than 100 characters (found 137)." source="com.puppycrawl.tools.checkstyle.checks.sizes.LineLengthCheck"/>
</file>
</checkstyle>'''

MOCK_CHECKSTYLE_XML_CLEAN = '''<?xml version="1.0" encoding="UTF-8"?>
<checkstyle version="8.41.1">
<file name="temporary_file.java">
</file>
</checkstyle>'''

def test_analyze_java_file_with_checkstyle_violations(mock_get_content, mocker):
    mock_get_content.return_value = VIOLATIONS_FILE_CONTENT
    mock_subprocess_run = mocker.patch('subprocess.run')
    mock_checkstyle_result = MagicMock()
    mock_checkstyle_result.stdout = MOCK_CHECKSTYLE_XML_VIOLATIONS
    mock_checkstyle_result.stderr = ""
    mock_checkstyle_result.returncode = 1
    mock_subprocess_run.return_value = mock_checkstyle_result
    file_info = {'filename': 'test_files/java/CheckstyleViolations.java', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_java_file(file_info, pr_data)
    mock_get_content.assert_called_once()
    mock_subprocess_run.assert_called_once()
    assert 'linting_issues' in findings
    assert len(findings['linting_issues']) == 5 # Based on MOCK_CHECKSTYLE_XML_VIOLATIONS
    issue1 = findings['linting_issues'][0]
    assert issue1['line'] == 5; assert issue1['code'] == 'TypeNameCheck'
    assert "Name 'incorrectClassName' must match pattern" in issue1['message']

def test_analyze_java_file_with_checkstyle_clean(mock_get_content, mocker):
    mock_get_content.return_value = CLEAN_FILE_CONTENT
    mock_subprocess_run = mocker.patch('subprocess.run')
    mock_checkstyle_result = MagicMock()
    mock_checkstyle_result.stdout = MOCK_CHECKSTYLE_XML_CLEAN
    mock_checkstyle_result.stderr = ""; mock_checkstyle_result.returncode = 0
    mock_subprocess_run.return_value = mock_checkstyle_result
    file_info = {'filename': 'test_files/java/CheckstyleClean.java', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_java_file(file_info, pr_data)
    mock_get_content.assert_called_once(); mock_subprocess_run.assert_called_once()
    assert 'linting_issues' in findings; assert len(findings['linting_issues']) == 0

def test_analyze_java_file_content_fetch_fails(mock_get_content, mocker): # This test existed
    mock_get_content.return_value = None
    mocker.patch('subprocess.run').assert_not_called() # Check Checkstyle is not run
    file_info = {'filename': 'test.java', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_java_file(file_info, pr_data)
    mock_get_content.assert_called_once()
    assert any("full content not fetched for Checkstyle" in imp for imp in findings['impacts'])
    assert findings['linting_issues'] == []

def test_analyze_java_file_security_keyword_found(mock_get_content): # This test existed
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

# --- Test for _analyze_other_file (keeping existing) ---
def test_analyze_other_file():
    file_info_other = {'filename': 'README.md', 'status': 'modified', 'patch': 'Some changes.'}
    findings = _analyze_other_file(file_info_other, {})
    assert "Non-code file changed: README.md" in findings['impacts'][0]
    assert not findings.get('linting_issues') or findings.get('linting_issues') == []
    assert not findings['security_issues']
    assert not findings['dependencies']
