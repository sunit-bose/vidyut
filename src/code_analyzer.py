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
        'linting_issues': [], 'raw_analysis_data': {}
    }

    owner = pr_data.get('owner')
    repo = pr_data.get('repo')
    head_sha = pr_data.get('head_sha')
    file_content = None

    if owner and repo and head_sha and filename:
        api_headers = {"Accept": "application/vnd.github.v3+json"}
        # TODO: Add GitHub token to headers
        file_content = get_file_content_at_ref(owner, repo, filename, head_sha, api_headers)
    else:
        findings['impacts'].append(f"Insufficient data to fetch full content for {filename}.")

    if not file_content:
        findings['impacts'].append(f"Python file {filename} changed, but full content not fetched for Flake8 (using patch for other checks if available).")
    else: # Full content is available for Flake8
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

    # Patch-based analysis (complementary to full file linting)
    patch_text = file_info.get('patch')
    if patch_text:
        findings['impacts'].append(f"Python file {filename} was modified (Status: {file_info.get('status', 'N/A')}).")

        # Define helper for changed line ranges within this scope as it's only used here
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
        if changed_line_info:
            findings['tests_suggestions'].append(f"Changes detected in {filename} (hunks: {len(changed_line_info)}). Consider specific unit tests.")
            findings['dependencies'].append(f"Review changes in {filename} for potential impacts on dependents (manual check).")
        else:
            findings['tests_suggestions'].append(f"Patch data for {filename} didn't yield specific line changes for targeted test suggestions.")

        for keyword in RUDIMENTARY_SECURITY_KEYWORDS:
            if keyword in patch_text:
                findings['security_issues'].append(f"Potential security keyword '{keyword}' found in changed lines.")
    else: # No patch text
        findings['impacts'].append(f"Python file {filename} (Status: {file_info.get('status', 'N/A')}) processed (no patch data for detailed change analysis).")

    if not findings['tests_suggestions'] and (findings['linting_issues'] or file_content): # If content was analyzed or linted
        findings['tests_suggestions'].append(f"Review linting/analysis results for {filename} and ensure test coverage.")
    elif not findings['tests_suggestions']: # Fallback if no content/linting and no patch-based suggestions
        findings['tests_suggestions'].append(f"Generic reminder: Ensure adequate test coverage for {filename}.")

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
        # TODO: Add GitHub token
        file_content = get_file_content_at_ref(owner, repo, filename, head_sha, api_headers)
    else:
        findings['impacts'].append(f"Insufficient data to fetch full content for {filename}.")

    if not file_content:
        findings['impacts'].append(f"Java file {filename} changed, but full content not fetched for Checkstyle (using patch for other checks if available).")
    else: # Full content available for Checkstyle
        tmp_file_path = ""
        checkstyle_jar_cmd = os.getenv("CHECKSTYLE_JAR", "checkstyle.jar")
        config_file_path = DEFAULT_CHECKSTYLE_CONFIG
        if not os.path.exists(config_file_path):
            findings['impacts'].append(f"Checkstyle config not found: {config_file_path}")
        else:
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False, encoding='utf-8') as tmp_file:
                    tmp_file.write(file_content)
                    tmp_file_path = tmp_file.name
                cmd = ['java', '-jar', checkstyle_jar_cmd, '-c', config_file_path, '-f', 'xml', tmp_file_path]
                process = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')
                if process.stderr:
                    print(f"Checkstyle stderr for {filename} (temp {tmp_file_path}): {process.stderr.strip()}")
                if process.stdout:
                    findings['linting_issues'] = _parse_checkstyle_xml_output(process.stdout, filename)
                elif not process.stderr:
                    findings['linting_issues'] = []
            except FileNotFoundError:
                findings['impacts'].append(f"Checkstyle/Java not found for {filename}. Ensure Java and Checkstyle JAR are accessible.")
            except Exception as e:
                findings['impacts'].append(f"Error running Checkstyle on {filename}: {str(e)}")
            finally:
                if tmp_file_path and os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)

    patch_text = file_info.get('patch')
    if patch_text:
        findings['impacts'].append(f"Java file {filename} was modified (Status: {file_info.get('status', 'N/A')}).")
        findings['tests_suggestions'].append(f"Review changes in {filename} and consider specific JUnit tests.")
        findings['dependencies'].append(f"Manual check: Review {filename} for impacts on dependents.")
        for keyword in RUDIMENTARY_SECURITY_KEYWORDS:
            if keyword in patch_text:
                findings['security_issues'].append(f"Potential security keyword '{keyword}' found in changed lines.")
    else:
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
        'linting_issues': [], 'raw_analysis_data': {} # Added linting_issues for consistency
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
    # Example Usage (with mock data for now) - Ensure pr_data includes owner, repo, head_sha for testing
    mock_pr_data_py = {
        'title': 'Test PR - Python Changes', 'owner': 'testowner', 'repo': 'testrepo', 'head_sha': 'testsha',
        'files_changed': [
            {'filename': 'src/module_a/file1.py', 'status': 'modified', 'patch': "print('hello')\n# TODO:SECURITY this is a test"},
            {'filename': 'docs/README.md', 'status': 'modified', 'patch': 'Updated docs'}
        ]
    }
    analysis_results_py = analyze_code_changes(mock_pr_data_py)
    print("\nPython PR Analysis Results:")
    print(f"Overall: {analysis_results_py['overall_summary']}")
    for finding in analysis_results_py['file_specific_findings']:
        print(f"File ({finding['language']}): {finding['file_path']}")
        for impact in finding['impacts']: print(f"  Impact: {impact}")
        for lint_issue in finding.get('linting_issues',[]): print(f"  Lint: L{lint_issue['line']} {lint_issue['code']} {lint_issue['message']}")
        for sec_issue in finding.get('security_issues',[]): print(f"  Security: {sec_issue}")
        for test_sugg in finding.get('tests_suggestions',[]): print(f"  Test: {test_sugg}")


    mock_pr_data_java = {
        'title': 'Test PR - Java Changes', 'owner': 'testowner', 'repo': 'testrepo', 'head_sha': 'testsha',
        'files_changed': [
            {'filename': 'com/example/Main.java', 'status': 'added', 'patch': 'public class Main {硬编码密码 secret_key = "test"; }'},
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
