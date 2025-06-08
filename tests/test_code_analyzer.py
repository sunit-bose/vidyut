import pytest
from src.code_analyzer import (
    analyze_code_changes, _analyze_python_file, _analyze_java_file, _analyze_other_file, _analyze_maven_pom,
    RUDIMENTARY_SECURITY_KEYWORDS,
    ANALYSIS_PYTHON_AST, ANALYSIS_FLAKE8, ANALYSIS_JAVA_CHECKSTYLE,
    ANALYSIS_JAVA_PARSER, ANALYSIS_SECURITY_KEYWORD_SCAN, ANALYSIS_PYTHON_TEST_STUB_GEN,
    ANALYSIS_MAVEN_POM, ALL_ANALYSES
)
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_get_content(mocker):
    return mocker.patch('src.code_analyzer.get_file_content_at_ref')

# --- Dispatch and Empty Data Tests ---
def test_analyze_code_changes_empty_pr_data(capsys):
    expected_empty_result = {'overall_summary': {'reuse_suggestions': [], 'solid_violations': [], 'general_security_reminders': []}, 'file_specific_findings': []}
    result_none = analyze_code_changes(None, [])
    assert result_none == expected_empty_result
    captured_none = capsys.readouterr(); assert "Error: Invalid PR data provided" in captured_none.out
    result_no_files_key = analyze_code_changes({'title': 'Test PR'}, [])
    assert result_no_files_key == expected_empty_result
    captured_no_files_key = capsys.readouterr(); assert "Error: Invalid PR data provided" in captured_no_files_key.out

def test_analyze_code_changes_dispatches_correctly_updated(mocker):
    mock_py = mocker.patch('src.code_analyzer._analyze_python_file', return_value={'language': 'python'})
    mock_java = mocker.patch('src.code_analyzer._analyze_java_file', return_value={'language': 'java'})
    mock_other = mocker.patch('src.code_analyzer._analyze_other_file', return_value={'language': 'other'})
    mock_pom = mocker.patch('src.code_analyzer._analyze_maven_pom', return_value={'language': 'maven_pom'})
    pr_data = {
        'title': 'Test Dispatch', 'owner':'o', 'repo':'r', 'head_sha':'s',
        'files_changed': [
            {'filename': 'test.py', 'status': 'modified', 'patch': '...'},
            {'filename': 'Test.java', 'status': 'added', 'patch': '...'},
            {'filename': 'pom.xml', 'status': 'modified', 'patch': '...'},
            {'filename': 'README.md', 'status': 'modified', 'patch': '...'}
        ]
    }
    results = analyze_code_changes(pr_data, analyses_to_run=ALL_ANALYSES)
    mock_py.assert_called_once_with(pr_data['files_changed'][0], pr_data, ALL_ANALYSES)
    mock_java.assert_called_once_with(pr_data['files_changed'][1], pr_data, ALL_ANALYSES)
    mock_pom.assert_called_once_with(pr_data['files_changed'][2], pr_data, ALL_ANALYSES)
    mock_other.assert_called_once_with(pr_data['files_changed'][3], pr_data)
    assert len(results['file_specific_findings']) == 4

# --- Python Analysis Tests ---
SAMPLE_PYTHON_CODE_SIMPLE_FUNC = "def hello(name):\n    print(f\"Hello, {name}\")"
SAMPLE_PYTHON_CODE_CLASS_METHOD = "class Greeter:\n    def __init__(self, greeting=\"Hello\"):\n        self.greeting = greeting\n\n    def greet(self, name):\n        return f\"{self.greeting}, {name}!\"\n\ndef standalone_func():\n    pass"
SAMPLE_PYTHON_CODE_WITH_DECORATORS_AND_BASES = "@my_decorator\n@another_decorator(arg=1)\nclass MyClass(Base1, Base2):\n    @classmethod\n    def factory(cls, value):\n        return cls(value)\n    \n    def __init__(self, value):\n        self.value = value"
SAMPLE_NEW_FUNCTION_CODE = "def new_util_func(param1, param2):\n    return param1 + param2"

def test_analyze_python_file_all_features_active(mock_get_content, mocker):
    mock_get_content.return_value = SAMPLE_NEW_FUNCTION_CODE
    mock_subprocess_run = mocker.patch('subprocess.run')
    mock_flake8_result = MagicMock(); mock_flake8_result.stdout = "temp.py:1:1: F401 unused"; mock_flake8_result.stderr = ""
    mock_subprocess_run.return_value = mock_flake8_result
    file_info = {'filename': 'src/my_utils.py', 'status': 'added',
                 'patch': '@@ -0,0 +1,2 @@\n+def new_util_func(param1, param2):\n+    return param1 + param2\n# TODO:SECURITY check this'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data, analyses_to_run=ALL_ANALYSES)

    assert any("Identified 1 new/modified Python definitions" in imp for imp in findings['impacts'])
    assert len(findings['python_definitions']) == 1
    assert len(findings['dependencies']) == 1
    assert "New Function `new_util_func(param1, param2)` (lines 1-2) in src/my_utils.py. Review usage and potential impacts." in findings['dependencies'][0]
    assert len(findings['tests_suggestions']) == 1
    assert "New function `new_util_func(param1, param2)` (lines 1-2) detected. Recommend tests for logic, args, outcomes." in findings['tests_suggestions'][0]
    assert len(findings['linting_issues']) == 1
    assert findings['linting_issues'][0]['code'] == 'F401'
    assert len(findings['security_issues']) == 1
    assert "Potential security keyword 'TODO:SECURITY' found" in findings['security_issues'][0]
    assert len(findings['python_test_stubs']) == 1
    assert "class TestNew_util_func(unittest.TestCase):" in findings['python_test_stubs'][0]['stub_code']

def test_analyze_python_file_content_fetch_fails(mock_get_content, mocker):
    mock_get_content.return_value = None
    mock_run = mocker.patch('subprocess.run')
    file_info = {'filename': 'test.py', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data, analyses_to_run=ALL_ANALYSES)
    mock_get_content.assert_called_once()
    mock_run.assert_not_called()
    expected_msg = "Python file test.py changed, but full content not fetched for analysis (using patch for other checks if available)."
    assert any(expected_msg == imp for imp in findings['impacts']), f"Expected impact message not found. Actual: {findings['impacts']}"
    assert findings['linting_issues'] == []

# --- Java Analysis Tests ---
SAMPLE_JAVA_CODE_FOR_PARSING = """
package com.example;
import java.util.List;
import static java.util.Collections.emptyList;

public class MyClass extends com.example.base.BaseClass implements com.example.common.MyInterface {
    private final String myField = "test";
    private int count;

    public MyClass(int initialCount) { // line 8
        this.count = initialCount;
    }

    /** Javadoc for method */
    public List<String> getItems(String filter) throws Exception { // line 13
        if (filter == null) {
            return emptyList();
        }
        return List.of(filter);
    }
    private void utilityHelper() {} // line 19
}
interface MyInterface {} // line 21
enum MyEnum { VAL1, VAL2 } // line 22
"""
VIOLATIONS_FILE_CONTENT = "public class incorrectClassName { public int PublicField; }"
CLEAN_FILE_CONTENT = "public class CorrectClassName { private int correctField; }"
MOCK_CHECKSTYLE_XML_VIOLATIONS = '''<?xml version="1.0" encoding="UTF-8"?>
<checkstyle version="8.41.1"><file name="t.java">
    <error line="1" column="14" severity="error" message="Name &apos;incorrectClassName&apos; must match pattern &apos;^[A-Z][a-zA-Z0-9]*$&apos;." source="TypeNameCheck"/>
    <error line="1" column="37" severity="error" message="Name &apos;PublicField&apos; must match pattern &apos;^[a-z]([a-zA-Z0-9_]*[a-zA-Z0-9])?$&apos;." source="MemberNameCheck"/>
</file></checkstyle>'''
MOCK_CHECKSTYLE_XML_CLEAN = '''<?xml version="1.0" encoding="UTF-8"?>
<checkstyle version="8.41.1"><file name="t.java"></file></checkstyle>'''


def test_analyze_java_file_parses_structure(mock_get_content):
    mock_get_content.return_value = SAMPLE_JAVA_CODE_FOR_PARSING
    file_info = {'filename': 'com/example/MyClass.java', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_java_file(file_info, pr_data, [ANALYSIS_JAVA_PARSER])
    defs = findings['java_definitions']
    pkg = next((d for d in defs if d['type'] == 'package'), None)
    assert pkg and pkg['name'] == 'com.example'
    imports = [d for d in defs if d['type'] == 'import']
    assert any(i['name'] == 'java.util.List' and not i['static'] for i in imports)
    cls_decl = next((d for d in defs if d['type'] == 'ClassDeclaration' and d['name'] == 'MyClass'), None)
    assert cls_decl is not None
    assert cls_decl['extends'] == 'com'
    assert 'com' in cls_decl.get('implements', [])
    get_items_method = next((m for m in cls_decl['methods'] if m['name'] == 'getItems'), None)
    assert get_items_method is not None
    assert get_items_method['return_type'] == 'List'

def test_analyze_java_file_identify_new_modified_definitions(mock_get_content):
    mock_get_content.return_value = SAMPLE_JAVA_CODE_FOR_PARSING
    # Patch that modifies the class declaration line (line 5 in SAMPLE_JAVA_CODE_FOR_PARSING)
    patch_text = "@@ -5,1 +5,1 @@ public class MyClass extends com.example.base.BaseClass implements com.example.common.MyInterface {"
    file_info = {'filename': 'com/example/MyClass.java', 'status': 'modified', 'patch': patch_text}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_java_file(file_info, pr_data, [ANALYSIS_JAVA_PARSER])

    my_class_node = next((d for d in findings['java_definitions'] if d['type'] == 'ClassDeclaration' and d['name'] == 'MyClass'), None)
    assert my_class_node is not None, "MyClass not found in java_definitions"
    assert my_class_node.get('change_type') == 'modified', "MyClass should be marked modified"

def test_analyze_java_file_specific_suggestions(mock_get_content):
    mock_get_content.return_value = SAMPLE_JAVA_CODE_FOR_PARSING
    file_info = {'filename': 'com/example/MyClass.java', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_java_file(file_info, pr_data, [ANALYSIS_JAVA_PARSER])
    assert any("New public class `MyClass`" in note for note in findings['dependencies'])
    assert any("New public method `getItems(String filter)`" in sugg for sugg in findings['tests_suggestions'])
    assert any("New public constructor for `MyClass(int initialCount)`" in sugg for sugg in findings['tests_suggestions'])

def test_analyze_java_file_content_fetch_fails(mock_get_content, mocker):
    mock_get_content.return_value = None
    mock_run = mocker.patch('subprocess.run')
    file_info = {'filename': 'test.java', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_java_file(file_info, pr_data, analyses_to_run=ALL_ANALYSES)
    mock_get_content.assert_called_once()
    mock_run.assert_not_called()
    expected_msg = "Java file test.java changed, but full content not fetched for analysis (using patch for other checks if available)."
    assert any(expected_msg == imp for imp in findings['impacts']), f"Expected impact message not found. Actual: {findings['impacts']}"
    assert findings['linting_issues'] == []

# --- Maven POM Analysis Tests ---
SAMPLE_POM_XML_CONTENT_WITH_NS = """
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>my-app</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-api</artifactId>
            <version>5.8.2</version>
        </dependency>
    </dependencies>
</project>
"""

def test_analyze_maven_pom_extracts_dependencies(mock_get_content):
    mock_get_content.return_value = SAMPLE_POM_XML_CONTENT_WITH_NS
    file_info = {'filename': 'pom.xml', 'status': 'added', 'patch': SAMPLE_POM_XML_CONTENT_WITH_NS}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_maven_pom(file_info, pr_data, [ANALYSIS_MAVEN_POM])
    assert 'build_dependency_changes' in findings
    assert len(findings['build_dependency_changes']) >= 1
    assert "New pom.xml added. Declared dependencies (1): org.junit.jupiter:junit-jupiter-api:5.8.2" in findings['build_dependency_changes'][0]

def test_analyze_maven_pom_patch_heuristics(mock_get_content):
    mock_get_content.return_value = "<project xmlns=\"http://maven.apache.org/POM/4.0.0\"><dependencies></dependencies></project>"
    patch_text_new_dep = "@@ -1,0 +1,3 @@\n+<dependency>\n+  <groupId>new</groupId>\n+</dependency>"
    file_info = {'filename': 'pom.xml', 'status': 'modified', 'patch': patch_text_new_dep}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_maven_pom(file_info, pr_data, [ANALYSIS_MAVEN_POM])
    assert any("Potentially 1 new/modified <dependency> block(s)" in note for note in findings['build_dependency_changes'])

# --- Conditional Execution & Other Tests ---
def test_analyze_python_file_conditional_flake8_skip(mock_get_content, mocker):
    mock_get_content.return_value = "print('hello')"
    mock_subprocess_run = mocker.patch('subprocess.run')
    file_info = {'filename': 'test.py', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data, analyses_to_run=[ANALYSIS_PYTHON_AST])
    mock_subprocess_run.assert_not_called()
    assert any("Flake8 linting skipped" in imp for imp in findings['impacts'])
    assert findings['linting_issues'] == []

def test_analyze_python_file_security_keyword_found_when_scan_active(mock_get_content):
    mock_get_content.return_value = "print('clean code')"
    file_info = {'filename': 'sec.py', 'status': 'modified', 'patch': '# TODO:SECURITY fix this later'}
    findings = _analyze_python_file(file_info, {'owner':'o','repo':'r','head_sha':'s'}, analyses_to_run=[ANALYSIS_SECURITY_KEYWORD_SCAN, ANALYSIS_PYTHON_AST])
    assert any("Potential security keyword 'TODO:SECURITY' found" in issue for issue in findings['security_issues'])

def test_analyze_java_file_security_keyword_found_when_scan_active(mock_get_content):
    mock_get_content.return_value = "class Clean {}"
    file_info_java_sec = {'filename': 'App.java', 'status': 'modified', 'patch': '// FIXME:SECURITY this is not safe'}
    findings = _analyze_java_file(file_info_java_sec, {'owner':'o','repo':'r','head_sha':'s'}, analyses_to_run=[ANALYSIS_SECURITY_KEYWORD_SCAN, ANALYSIS_JAVA_PARSER])
    assert any("Potential security keyword 'FIXME:SECURITY' found" in issue for issue in findings['security_issues'])

def test_analyze_other_file():
    file_info_other = {'filename': 'README.md', 'status': 'modified', 'patch': 'Some changes.'}
    findings = _analyze_other_file(file_info_other, {})
    assert "Non-code file changed: README.md" in findings['impacts'][0]
    assert not findings.get('linting_issues') or findings.get('linting_issues') == []

def test_analyze_java_file_with_checkstyle_violations_adapted(mock_get_content, mocker):
    mock_get_content.return_value = VIOLATIONS_FILE_CONTENT
    mock_subprocess_run = mocker.patch('subprocess.run')
    mock_checkstyle_result = MagicMock()
    mock_checkstyle_result.stdout = MOCK_CHECKSTYLE_XML_VIOLATIONS
    mock_checkstyle_result.stderr = ""; mock_checkstyle_result.returncode = 1
    mock_subprocess_run.return_value = mock_checkstyle_result
    file_info = {'filename': 'test_files/java/CheckstyleViolations.java', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_java_file(file_info, pr_data, analyses_to_run=[ANALYSIS_JAVA_CHECKSTYLE])
    mock_get_content.assert_called_once()
    mock_subprocess_run.assert_called_once()
    assert 'linting_issues' in findings
    assert len(findings['linting_issues']) == 2
    issue1 = findings['linting_issues'][0]
    assert issue1['line'] == 1; assert issue1['code'] == 'TypeNameCheck'

def test_analyze_java_file_with_checkstyle_clean_adapted(mock_get_content, mocker):
    mock_get_content.return_value = CLEAN_FILE_CONTENT
    mock_subprocess_run = mocker.patch('subprocess.run')
    mock_checkstyle_result = MagicMock(); mock_checkstyle_result.stdout = MOCK_CHECKSTYLE_XML_CLEAN
    mock_checkstyle_result.stderr = ""; mock_checkstyle_result.returncode = 0
    mock_subprocess_run.return_value = mock_checkstyle_result
    file_info = {'filename': 'test_files/java/CheckstyleClean.java', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_java_file(file_info, pr_data, analyses_to_run=[ANALYSIS_JAVA_CHECKSTYLE])
    mock_get_content.assert_called_once(); mock_subprocess_run.assert_called_once()
    assert 'linting_issues' in findings; assert len(findings['linting_issues']) == 0

def test_analyze_python_file_decorators_and_bases(mock_get_content): # Preserved
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_WITH_DECORATORS_AND_BASES
    file_info = {'filename': 'complex.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data, analyses_to_run=[ANALYSIS_PYTHON_AST])
    defs = findings['python_definitions']
    my_class_def = next((d for d in defs if d['name'] == 'MyClass'), None)
    assert my_class_def is not None; assert 'my_decorator' in my_class_def['decorators']
    assert any("Call(func=Name(id='another_decorator'" in dec for dec in my_class_def['decorators'] if isinstance(dec, str))
    assert my_class_def['bases'] == ['Base1', 'Base2']
    factory_method = next((d for d in defs if d['name'] == 'factory'), None)
    assert factory_method is not None; assert 'classmethod' in factory_method['decorators']

def test_analyze_python_file_specific_dependency_notes_ast_on(mock_get_content): # Preserved
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_SIMPLE_FUNC
    file_info = {'filename': 'hello.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data, analyses_to_run=[ANALYSIS_PYTHON_AST])
    assert 'dependencies' in findings; assert len(findings['dependencies']) >= 1
    assert any("New Function `hello(name)`" in dep for dep in findings['dependencies'])

def test_analyze_python_file_specific_test_suggestions_ast_on(mock_get_content): # Preserved
    mock_get_content.return_value = SAMPLE_PYTHON_CODE_CLASS_METHOD
    file_info = {'filename': 'greeter.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data, analyses_to_run=[ANALYSIS_PYTHON_AST])
    assert 'tests_suggestions' in findings; assert len(findings['tests_suggestions']) == 4

def test_analyze_python_file_test_stub_generation_new_function(mock_get_content): # Preserved
    mock_get_content.return_value = SAMPLE_NEW_FUNCTION_CODE
    file_info = {'filename': 'src/my_utils.py', 'status': 'added',
                 'patch': '@@ -0,0 +1,2 @@\n+def new_util_func(param1, param2):\n+    return param1 + param2'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    analyses = [ANALYSIS_PYTHON_AST, ANALYSIS_PYTHON_TEST_STUB_GEN]
    findings = _analyze_python_file(file_info, pr_data, analyses_to_run=analyses)
    assert 'python_test_stubs' in findings; assert len(findings['python_test_stubs']) == 1
    stub_info = findings['python_test_stubs'][0]
    assert stub_info['target_definition_name'] == 'new_util_func'
    assert "class TestNew_util_func(unittest.TestCase):" in stub_info['stub_code']

def test_analyze_python_file_test_stub_gen_disabled(mock_get_content): # Preserved
    mock_get_content.return_value = SAMPLE_NEW_FUNCTION_CODE
    file_info = {'filename': 'src/my_utils.py', 'status': 'added', 'patch': '...'}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data, analyses_to_run=[ANALYSIS_PYTHON_AST])
    assert findings.get('python_test_stubs') == []

def test_analyze_python_file_fallback_test_suggestion(mock_get_content): # Preserved
    mock_get_content.return_value = "print('just some script code')"
    patch_text = "@@ -1,0 +1,1 @@\n+print('just some script code')"
    file_info = {'filename': 'script.py', 'status': 'added', 'patch': patch_text}
    pr_data = {'owner': 'o', 'repo': 'r', 'head_sha': 's'}
    findings = _analyze_python_file(file_info, pr_data, [ANALYSIS_PYTHON_AST, ANALYSIS_FLAKE8]) # Run relevant analyses
    assert not findings['python_definitions']
    expected_suggestion = "Changes detected in script.py (hunks: 1). Consider specific unit tests for modified logic based on patch."
    assert any(expected_suggestion in sugg for sugg in findings['tests_suggestions'])
