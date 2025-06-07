# src/code_analyzer.py

import ast
import re # For parsing line numbers from patch
import javalang # Added for Java analysis
import subprocess
import tempfile
import os
import xml.etree.ElementTree as ET # Added for Checkstyle XML parsing

# Rudimentary security keywords to scan for in patches
RUDIMENTARY_SECURITY_KEYWORDS = [
    "TODO:SECURITY",
    "FIXME:SECURITY",
    "HARDCODED_PASSWORD",
    "hardcoded_password",
    "Password=",
    "password =",
    "secret_key =",
    "SECRET_KEY =",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
]

# Import for fetching file content
if __package__ is None or __package__ == '':
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from src.pr_parser import get_file_content_at_ref
else:
    from .pr_parser import get_file_content_at_ref

DEFAULT_CHECKSTYLE_CONFIG = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', 'config', 'google_checks.xml'
))

def _parse_flake8_output(output_str: str, original_filename: str) -> list:
    linting_issues = []
    for line in output_str.splitlines():
        match = re.match(r"^[^:]+:([0-9]+):([0-9]+): ([A-Z][0-9]+) (.*)$", line)
        if match:
            linting_issues.append({
                "file": original_filename, "line": int(match.group(1)),
                "column": int(match.group(2)), "code": match.group(3),
                "message": match.group(4).strip()
            })
        elif line.strip():
            linting_issues.append({
                "file": original_filename, "line": 0, "column": 0,
                "code": "FLAKE8_PARSE_ERROR", "message": f"Unparseable Flake8 output line: {line.strip()}"
            })
    return linting_issues

def _parse_checkstyle_xml_output(xml_str: str, original_filename: str) -> list:
    linting_issues = []
    if not xml_str: return linting_issues
    try:
        root = ET.fromstring(xml_str)
        for file_node in root.findall('file'):
            for error_node in file_node.findall('error'):
                try:
                    linting_issues.append({
                        "file": original_filename,
                        "line": int(error_node.get('line', '0')),
                        "column": int(error_node.get('column', '0')),
                        "code": error_node.get('source', '').split('.')[-1] or 'CheckstyleError',
                        "message": error_node.get('message', 'No message'),
                        "severity": error_node.get('severity', 'info')
                    })
                except ValueError as ve:
                    linting_issues.append({
                        "file": original_filename, "line": 0, "column": 0, "code": "PARSE_ERROR",
                        "message": f"Error parsing Checkstyle error node: {ve}. Node: {ET.tostring(error_node, encoding='unicode')}"
                    })
    except ET.ParseError as e:
        linting_issues.append({
            "file": original_filename, "line": 0, "column": 0, "code": "XML_PARSE_ERROR",
            "message": f"Failed to parse Checkstyle XML output: {e}"
        })
    return linting_issues

def _analyze_python_file(file_info, pr_data):
    filename = file_info.get('filename')
    findings = {
        'file_path': filename, 'language': 'python', 'impacts': [],
        'dependencies': [], 'tests_suggestions': [], 'security_issues': [],
        'linting_issues': [], 'python_definitions': [],
        'raw_analysis_data': {}
    }

    owner = pr_data.get('owner')
    repo = pr_data.get('repo')
    head_sha = pr_data.get('head_sha')
    file_content = None

    if owner and repo and head_sha and filename:
        api_headers = {"Accept": "application/vnd.github.v3+json"}
        file_content = get_file_content_at_ref(owner, repo, filename, head_sha, api_headers)
    else:
        findings['impacts'].append(f"Insufficient data to fetch full content for {filename}.")

    definitions_from_ast = []
    if file_content:
        try:
            tree = ast.parse(file_content, filename=filename)
            for node in ast.walk(tree):
                definition_info = None
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [arg.arg for arg in node.args.args]
                    end_line = getattr(node, 'end_lineno', node.lineno)
                    def_type = "function"
                    if args and args[0] in ['self', 'cls']: def_type = "method"
                    definition_info = {
                        "name": node.name, "type": def_type,
                        "start_line": node.lineno, "end_line": end_line if end_line is not None else node.lineno,
                        "args": args,
                        "decorators": [dec.id for dec in node.decorator_list if isinstance(dec, ast.Name)] + \
                                      [ast.dump(dec) for dec in node.decorator_list if not isinstance(dec, ast.Name)]
                    }
                elif isinstance(node, ast.ClassDef):
                    definition_info = {
                        "name": node.name, "type": "class",
                        "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', node.lineno),
                        "methods": [],
                        "bases": [base.id for base in node.bases if isinstance(base, ast.Name)],
                        "decorators": [dec.id for dec in node.decorator_list if isinstance(dec, ast.Name)] + \
                                      [ast.dump(dec) for dec in node.decorator_list if not isinstance(dec, ast.Name)]
                    }
                if definition_info:
                    definitions_from_ast.append(definition_info)
            if not definitions_from_ast:
                 findings['impacts'].append(f"AST parsed {filename}, but no class/function definitions identified.")
        except SyntaxError as e:
            findings['impacts'].append(f"AST SyntaxError in {filename}: {e.msg} (line {e.lineno}). Linting may be affected.")
        except Exception as e:
            findings['impacts'].append(f"AST parsing error in {filename}: {str(e)}. Linting may be affected.")

        tmp_file_path = ""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name
            process = subprocess.run(
                ['flake8', tmp_file_path], capture_output=True, text=True, check=False, encoding='utf-8'
            )
            findings['linting_issues'] = _parse_flake8_output(process.stdout, filename)
            if process.stderr:
                print(f"Flake8 stderr for {filename} (temp {tmp_file_path}): {process.stderr.strip()}")
        except FileNotFoundError:
            findings['impacts'].append(f"Flake8 command not found for {filename}.")
        except Exception as e:
            findings['impacts'].append(f"Error running Flake8 on {filename}: {str(e)}")
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
    else:
        findings['impacts'].append(f"Python file {filename} changed, but full content not fetched for AST parsing and Flake8 analysis.")

    patch_text = file_info.get('patch')
    changed_line_info = []
    file_status = file_info.get('status', 'modified')

    if patch_text:
        if not any(f"AST parsed" in imp for imp in findings['impacts']) and not file_content:
            findings['impacts'].append(f"Python file {filename} was modified (Status: {file_info.get('status', 'N/A')}).")

        def get_changed_line_ranges(patch_text_local):
            ranges_local = []
            for line_local in patch_text_local.splitlines():
                if line_local.startswith("@@"):
                    match_local = re.search(r"\+([0-9]+)(?:,([0-9]+))?", line_local)
                    if match_local:
                        start_line = int(match_local.group(1))
                        length = int(match_local.group(2) or 1)
                        if length > 0:
                           ranges_local.append((start_line, length))
            return ranges_local
        changed_line_info = get_changed_line_ranges(patch_text)

        for keyword in RUDIMENTARY_SECURITY_KEYWORDS:
            if keyword in patch_text:
                findings['security_issues'].append(f"Potential security keyword '{keyword}' found in changed lines (patch scan).")
    else:
        if not findings['impacts']:
            findings['impacts'].append(f"Python file {filename} (Status: {file_info.get('status', 'N/A')}) processed (no patch data).")

    modified_definitions_count = 0
    if definitions_from_ast:
        findings['impacts'] = [imp for imp in findings['impacts']
                               if not imp.startswith("AST parsed") and not imp.startswith("Could not parse Python file with AST")]

        for definition in definitions_from_ast:
            def_start = definition['start_line']
            def_end = definition['end_line']
            change_type = None
            if file_status == 'added':
                change_type = 'new'
            elif changed_line_info:
                for hunk_start, hunk_length in changed_line_info:
                    hunk_end = hunk_start + hunk_length -1
                    if max(def_start, hunk_start) <= min(def_end, hunk_end):
                        change_type = 'modified'
                        break
            if change_type:
                definition['change_type'] = change_type
                findings['python_definitions'].append(definition)
                modified_definitions_count +=1

        if modified_definitions_count > 0:
            findings['impacts'].append(
                f"Identified {modified_definitions_count} new/modified Python definitions in {filename} within changed code sections."
            )
        elif definitions_from_ast:
            findings['impacts'].append(
                f"AST parsed {len(definitions_from_ast)} Python definitions in {filename}, but none appear directly in changed code lines based on patch."
            )

    findings['dependencies'] = []
    for definition_info in findings.get('python_definitions', []):
        name = definition_info['name']
        def_type = definition_info['type']
        start_line = definition_info['start_line']
        end_line = definition_info['end_line']
        args_list = definition_info.get('args', [])
        change = definition_info.get('change_type', 'changed')
        args_str = ", ".join(args_list)
        description = ""
        if def_type == "method":
            description = f"Method `{name}({args_str})` (lines {start_line}-{end_line}) in {filename}"
        elif def_type == "function":
            description = f"Function `{name}({args_str})` (lines {start_line}-{end_line}) in {filename}"
        elif def_type == "class":
            bases = definition_info.get('bases', [])
            bases_str = f"(inherits: {', '.join(bases)})" if bases else ""
            description = f"Class `{name}` {bases_str} (lines {start_line}-{end_line}) in {filename}"

        change_verb = "New" if change == "new" else "Modified"
        dependency_note = f"{change_verb} {description}. Review its usage and potential impacts on callers or dependent components."
        findings['dependencies'].append(dependency_note)

    findings['tests_suggestions'] = []
    for definition_info in findings.get('python_definitions', []):
        name = definition_info['name']
        def_type = definition_info['type']
        start_line = definition_info['start_line']
        end_line = definition_info['end_line']
        args_list = definition_info.get('args', [])
        change = definition_info.get('change_type', 'changed')
        args_str = ", ".join(args_list)
        change_desc = "New" if change == "new" else "Modified"
        suggestion_text = ""
        if def_type == "function":
            suggestion_text = (f"{change_desc} function `{name}({args_str})` (lines {start_line}-{end_line}) detected in {filename}. "
                             f"Recommend adding/reviewing unit tests that cover its core logic, argument variations, and expected outcomes.")
        elif def_type == "method":
            suggestion_text = (f"{change_desc} method `{name}({args_str})` (lines {start_line}-{end_line}) detected in {filename}. "
                             f"Recommend adding/reviewing unit tests for this method, focusing on changes, class state interaction, and input scenarios.")
        elif def_type == "class":
            suggestion_text = (f"{change_desc} class `{name}` (lines {start_line}-{end_line}) detected in {filename}. "
                             f"Recommend creating/reviewing a comprehensive test suite for this class (constructor, public methods, state, interactions).")
        if suggestion_text:
            findings['tests_suggestions'].append(suggestion_text)

    if not findings['tests_suggestions']:
        if changed_line_info:
            findings['tests_suggestions'].append(
                f"Changes detected in {filename} (hunks: {len(changed_line_info)}). Consider specific unit tests for modified logic based on patch."
            )
        elif file_status == 'added' and file_content and not definitions_from_ast:
             findings['tests_suggestions'].append(
                f"{filename} was added and contains executable code. Ensure appropriate tests are in place for its behavior."
            )
        elif findings['linting_issues']:
            findings['tests_suggestions'].append(f"Review linting issues for {filename} and ensure test coverage for overall changes.")
        elif file_content :
             findings['tests_suggestions'].append(f"Generic reminder: Ensure adequate test coverage for changes in {filename}.")
        elif not file_content and patch_text:
             findings['tests_suggestions'].append(f"Full content not analyzed for {filename}. Review patch changes and ensure test coverage.")
        else:
            findings['tests_suggestions'].append(f"No content or patch data for {filename} to provide specific test suggestions. Review file status and ensure coverage if it's part of PR.")

    return findings

def _analyze_java_file(file_info, pr_data):
    filename = file_info.get('filename')
    findings = {
        'file_path': filename, 'language': 'java', 'impacts': [],
        'dependencies': [], 'tests_suggestions': [], 'security_issues': [],
        'linting_issues': [], 'raw_analysis_data': {}
    }
    owner = pr_data.get('owner')
    repo = pr_data.get('repo')
    head_sha = pr_data.get('head_sha')
    file_content = None
    if owner and repo and head_sha and filename:
        api_headers = {"Accept": "application/vnd.github.v3+json"}
        file_content = get_file_content_at_ref(owner, repo, filename, head_sha, api_headers)
    else:
        findings['impacts'].append(f"Insufficient data to fetch full content for {filename}.")

    if not file_content:
        findings['impacts'].append(f"Java file {filename} changed, but full content not fetched for Checkstyle (using patch for other checks if available).")
        patch_text_for_sec_scan = file_info.get('patch')
        if patch_text_for_sec_scan:
            for keyword in RUDIMENTARY_SECURITY_KEYWORDS:
                if keyword in patch_text_for_sec_scan:
                    findings['security_issues'].append(f"Potential security keyword '{keyword}' found in patch.")
        if not findings['tests_suggestions']:
             findings['tests_suggestions'].append(f"Content for {filename} not available for full analysis; ensure test coverage based on changes.")
        return findings
    else:
        tmp_file_path = ""
        checkstyle_jar_cmd = os.getenv("CHECKSTYLE_JAR", "checkstyle.jar")
        config_file_path = DEFAULT_CHECKSTYLE_CONFIG
        if not os.path.exists(config_file_path):
            findings['impacts'].append(f"Checkstyle config file not found at {config_file_path} for {filename}.")
        else:
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False, encoding='utf-8') as tmp_file:
                    tmp_file.write(file_content)
                    tmp_file_path = tmp_file.name
                cmd = ['java', '-jar', checkstyle_jar_cmd, '-c', config_file_path, '-f', 'xml', tmp_file_path]
                process = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')

                stderr_output = process.stderr.strip()
                if stderr_output:
                    print(f"Checkstyle stderr for {filename} (temp {tmp_file_path}): {stderr_output}")
                    # Heuristic for operational error
                    if "Exception" in stderr_output or "Error" in stderr_output or "Could not" in stderr_output:
                        findings['impacts'].append(
                            f"Checkstyle encountered an operational error for {filename} (see console logs). " +
                            "This may indicate a configuration issue with Checkstyle, Java, or the Checkstyle JAR."
                        )

                if process.stdout:
                    findings['linting_issues'] = _parse_checkstyle_xml_output(process.stdout, filename)
                elif not stderr_output: # No stdout and no stderr -> assume no issues found
                    findings['linting_issues'] = []
            except FileNotFoundError:
                findings['impacts'].append(
                   f"Checkstyle execution failed for {filename}. Ensure Java is installed and " +
                   f"'{checkstyle_jar_cmd}' (Checkstyle JAR) is accessible. " +
                   f"Set CHECKSTYLE_JAR environment variable or ensure '{checkstyle_jar_cmd}' is in system PATH."
                )
            except Exception as e:
                findings['impacts'].append(f"Error running Checkstyle on {filename}: {str(e)}")
            finally:
                if tmp_file_path and os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)

    patch_text = file_info.get('patch')
    if patch_text:
        if not any(f"Successfully parsed Java file {filename}" in imp for imp in findings['impacts']) and \
           not any(f"Could not parse Java file {filename}" in imp for imp in findings['impacts']):
            findings['impacts'].append(f"Java file {filename} was modified (Status: {file_info.get('status', 'N/A')}).")
        current_test_suggestions = findings.get('tests_suggestions', [])
        if not current_test_suggestions:
            current_test_suggestions.append(f"Review changes in {filename} and consider specific JUnit tests.")
        findings['tests_suggestions'] = current_test_suggestions
        if not findings.get('dependencies'):
            findings['dependencies'].append(f"Manual check: Review {filename} for impacts on dependents.")
        for keyword in RUDIMENTARY_SECURITY_KEYWORDS:
            if keyword in patch_text:
                findings['security_issues'].append(f"Potential security keyword '{keyword}' found in changed lines.")
    else:
        if not findings['impacts']:
            findings['impacts'].append(f"Java file {filename} (Status: {file_info.get('status', 'N/A')}) processed (no patch data for detailed change analysis).")

    if not findings['tests_suggestions'] and (findings['linting_issues'] or file_content):
        findings['tests_suggestions'].append(f"Review linting/analysis results for {filename} and ensure test coverage.")
    elif not findings['tests_suggestions']:
        findings['tests_suggestions'].append(f"Generic reminder: Ensure adequate JUnit test coverage for {filename}.")
    return findings

def _analyze_other_file(file_info, pr_data):
    findings = {
        'file_path': file_info.get('filename'), 'language': 'other',
        'impacts': [f"Non-code file changed: {file_info['filename']} (Status: {file_info.get('status', 'N/A')})"],
        'dependencies': [], 'tests_suggestions': [], 'security_issues': [],
        'linting_issues': [], 'raw_analysis_data': {}
    }
    return findings

def analyze_code_changes(pr_data):
    if not pr_data or 'files_changed' not in pr_data:
        print("Error: Invalid PR data provided for analysis in analyze_code_changes.")
        return {
            'overall_summary': {'reuse_suggestions': [], 'solid_violations': [], 'general_security_reminders': []},
            'file_specific_findings': []
        }
    print(f"Analyzing PR (multi-language): {pr_data.get('title', 'N/A')}")
    file_specific_findings_list = []
    for file_info in pr_data.get('files_changed', []):
        filename = file_info.get('filename', '')
        if not filename: continue
        if filename.endswith('.py'):
            findings = _analyze_python_file(file_info, pr_data)
        elif filename.endswith('.java'):
            findings = _analyze_java_file(file_info, pr_data)
        else:
            findings = _analyze_other_file(file_info, pr_data)
        file_specific_findings_list.append(findings)

    overall_reuse_suggestions = []
    if len(pr_data.get('files_changed', [])) > 1:
        overall_reuse_suggestions.append("Consider if there are common patterns across the changed files that could be abstracted globally.")
    overall_solid_violations = ["Reminder: Review all code changes for adherence to SOLID principles."]
    general_security_reminders = []
    if any(f_item.get('language') in ['python', 'java'] for f_item in file_specific_findings_list):
         general_security_reminders.append("Overall Security Reminder: Review changes for potential security vulnerabilities (e.g., input validation, proper auth).")
    print("Code analysis complete (multi-language dispatch structure).")
    return {
        'overall_summary': {
            'reuse_suggestions': overall_reuse_suggestions,
            'solid_violations': overall_solid_violations,
            'general_security_reminders': general_security_reminders
        },
        'file_specific_findings': file_specific_findings_list
    }

if __name__ == '__main__':
    mock_pr_data_py = {
        'title': 'Test PR - Python Changes', 'owner': 'testowner', 'repo': 'testrepo', 'head_sha': 'testsha',
        'files_changed': [
            {'filename': 'src/module_a/file1.py', 'status': 'modified', 'patch': "print('hello')\n# TODO:SECURITY this is a test\ndef my_func(): pass\nclass MyClass: pass"},
            {'filename': 'docs/README.md', 'status': 'modified', 'patch': 'Updated docs'}
        ]
    }
    analysis_results_py = analyze_code_changes(mock_pr_data_py)
    print("\nPython PR Analysis Results:")
    print(f"Overall: {analysis_results_py['overall_summary']}")
    for finding in analysis_results_py['file_specific_findings']:
        print(f"File ({finding['language']}): {finding['file_path']}")
        for impact in finding['impacts']: print(f"  Impact: {impact}")
        if finding.get('python_definitions'):
            print(f"  Python Definitions (New/Modified): {finding['python_definitions']}")
        for lint_issue in finding.get('linting_issues',[]): print(f"  Lint: L{lint_issue['line']} {lint_issue['code']} {lint_issue['message']}")
        for sec_issue in finding.get('security_issues',[]): print(f"  Security: {sec_issue}")
        for test_sugg in finding.get('tests_suggestions',[]): print(f"  Test: {test_sugg}")
        for dep_note in finding.get('dependencies',[]): print(f"  Dependency: {dep_note}")

    mock_pr_data_java = {
        'title': 'Test PR - Java Changes', 'owner': 'testowner', 'repo': 'testrepo', 'head_sha': 'testsha',
        'files_changed': [
            {'filename': 'com/example/Main.java', 'status': 'added', 'patch': 'public class Main { private String secret_key = "test"; }'},
            {'filename': 'com/example/Util.java', 'status': 'modified', 'patch': '// A util class'},
        ]
    }
    analysis_results_java = analyze_code_changes(mock_pr_data_java)
    print("\nJava PR Analysis Results:")
    print(f"Overall: {analysis_results_java['overall_summary']}")
    for finding in analysis_results_java['file_specific_findings']:
        print(f"File ({finding['language']}): {finding['file_path']}")
        for impact in finding['impacts']: print(f"  Impact: {impact}")
        for lint_issue in finding.get('linting_issues',[]): print(f"  Lint: L{lint_issue['line']} {lint_issue['code']} {lint_issue['message']}")
        for sec_issue in finding.get('security_issues',[]): print(f"  Security: {sec_issue}")
        for test_sugg in finding.get('tests_suggestions',[]): print(f"  Test: {test_sugg}")
        for dep_note in finding.get('dependencies',[]): print(f"  Dependency: {dep_note}")
