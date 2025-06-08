# src/code_analyzer.py

import ast
import re # For parsing line numbers from patch
import javalang # Added for Java analysis
import subprocess
import tempfile
import os
import xml.etree.ElementTree as ET # Added for Checkstyle XML parsing
from typing import List, Dict, Any # For type hints

# Analysis Type Constants
ANALYSIS_PYTHON_AST = "python_ast"
ANALYSIS_FLAKE8 = "flake8"
ANALYSIS_JAVA_CHECKSTYLE = "checkstyle"
ANALYSIS_JAVA_PARSER = "java_parser"
ANALYSIS_SECURITY_KEYWORD_SCAN = "security_scan"
ANALYSIS_PYTHON_TEST_STUB_GEN = "python_test_stubs"

ALL_ANALYSES = [
    ANALYSIS_PYTHON_AST,
    ANALYSIS_FLAKE8,
    ANALYSIS_JAVA_CHECKSTYLE,
    ANALYSIS_JAVA_PARSER,
    ANALYSIS_SECURITY_KEYWORD_SCAN,
    ANALYSIS_PYTHON_TEST_STUB_GEN,
]

DEFAULT_ANALYSES_TO_RUN = [
    ANALYSIS_PYTHON_AST,
    ANALYSIS_FLAKE8,
    ANALYSIS_JAVA_CHECKSTYLE,
    ANALYSIS_SECURITY_KEYWORD_SCAN,
]

# Rudimentary security keywords (ensure it's defined)
RUDIMENTARY_SECURITY_KEYWORDS = [
    "TODO:SECURITY", "FIXME:SECURITY", "HARDCODED_PASSWORD", "hardcoded_password",
    "Password=", "password =", "secret_key =", "SECRET_KEY =",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
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

def _parse_flake8_output(output_str: str, original_filename: str) -> List[Dict[str, Any]]:
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

def _parse_checkstyle_xml_output(xml_str: str, original_filename: str) -> List[Dict[str, Any]]:
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

def _analyze_python_file(file_info: Dict[str, Any], pr_data: Dict[str, Any], analyses_to_run: List[str]) -> Dict[str, Any]:
    filename = file_info.get('filename')
    findings = {
        'file_path': filename, 'language': 'python', 'impacts': [],
        'dependencies': [], 'tests_suggestions': [], 'security_issues': [],
        'linting_issues': [], 'python_definitions': [],
        'python_test_stubs': [],
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

    # This is the primary message if content fetching fails.
    if not file_content:
        findings['impacts'].append(f"Python file {filename} changed, but full content not fetched for AST parsing and Flake8 analysis (using patch for other checks if available).")

    definitions_from_ast = []
    if file_content and ANALYSIS_PYTHON_AST in analyses_to_run:
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
                 findings['impacts'].append(f"Python AST analysis run on {filename}, but no class/function definitions identified.")
        except SyntaxError as e:
            findings['impacts'].append(f"Python AST SyntaxError in {filename}: {e.msg} (line {e.lineno}).")
        except Exception as e:
            findings['impacts'].append(f"Python AST parsing error in {filename}: {str(e)}.")
    elif ANALYSIS_PYTHON_AST not in analyses_to_run:
        findings['impacts'].append(f"Python AST analysis skipped for {filename}.")
    # If content fetch failed but AST was requested, the earlier "not fetched" message covers it.

    if file_content and ANALYSIS_FLAKE8 in analyses_to_run:
        tmp_file_path = ""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(file_content); tmp_file_path = tmp_file.name
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
            if tmp_file_path and os.path.exists(tmp_file_path): os.remove(tmp_file_path)
    elif ANALYSIS_FLAKE8 not in analyses_to_run:
        findings['impacts'].append(f"Flake8 linting skipped for {filename}.")
    elif not file_content and ANALYSIS_FLAKE8 in analyses_to_run :
        findings['impacts'].append(f"Flake8 linting skipped for {filename} because full content was not available.")

    patch_text = file_info.get('patch')
    changed_line_info = []
    file_status = file_info.get('status', 'modified')

    if patch_text:
        # Add general "modified" impact only if AST didn't run (or failed) and content wasn't there to clarify status.
        # If AST ran, it would have added more specific messages.
        if not file_content and not any(f"AST parsed" in imp for imp in findings['impacts']) and ANALYSIS_PYTHON_AST in analyses_to_run :
            findings['impacts'].append(f"Python file {filename} was modified (Status: {file_info.get('status', 'N/A')}, patch available).")

        def get_changed_line_ranges(patch_text_local):
            ranges_local = [];
            for line_local in patch_text_local.splitlines():
                if line_local.startswith("@@"):
                    match_local = re.search(r"\+([0-9]+)(?:,([0-9]+))?", line_local)
                    if match_local:
                        start_line = int(match_local.group(1)); length = int(match_local.group(2) or 1)
                        if length > 0: ranges_local.append((start_line, length))
            return ranges_local
        changed_line_info = get_changed_line_ranges(patch_text)

        if ANALYSIS_SECURITY_KEYWORD_SCAN in analyses_to_run:
            for keyword in RUDIMENTARY_SECURITY_KEYWORDS:
                if keyword in patch_text:
                    findings['security_issues'].append(f"Potential security keyword '{keyword}' found in changed lines (patch scan).")
    elif not findings['impacts']: # No patch, and no prior impact messages (e.g. from content fetch failure)
        findings['impacts'].append(f"Python file {filename} (Status: {file_info.get('status', 'N/A')}) processed (no patch data).")

    if ANALYSIS_PYTHON_AST in analyses_to_run and definitions_from_ast:
        modified_definitions_count = 0
        # Filter out preliminary AST messages to replace with more specific ones.
        findings['impacts'] = [imp for imp in findings['impacts']
                               if not imp.startswith("AST parsed") and not imp.startswith("Python AST SyntaxError") and not imp.startswith("Python AST parsing error")]

        for definition in definitions_from_ast:
            def_start = definition['start_line']; def_end = definition['end_line']; change_type = None
            if file_status == 'added': change_type = 'new'
            elif changed_line_info:
                for hunk_start, hunk_length in changed_line_info:
                    hunk_end = hunk_start + hunk_length -1
                    if max(def_start, hunk_start) <= min(def_end, hunk_end): change_type = 'modified'; break
            if change_type:
                definition['change_type'] = change_type
                findings['python_definitions'].append(definition); modified_definitions_count +=1

        if modified_definitions_count > 0:
            findings['impacts'].append(f"Identified {modified_definitions_count} new/modified Python definitions in {filename} within changed code sections.")
        elif definitions_from_ast:
            findings['impacts'].append(f"AST parsed {len(definitions_from_ast)} definitions in {filename}, but none appear directly in changed code lines based on patch.")

        for definition_info in findings['python_definitions']:
            name = definition_info['name']; def_type = definition_info['type']; start_line = definition_info['start_line']
            end_line = definition_info['end_line']; args_list = definition_info.get('args', [])
            change = definition_info.get('change_type', 'changed'); args_str = ", ".join(args_list); description = ""
            if def_type == "method": description = f"Method `{name}({args_str})` (lines {start_line}-{end_line}) in {filename}"
            elif def_type == "function": description = f"Function `{name}({args_str})` (lines {start_line}-{end_line}) in {filename}"
            elif def_type == "class":
                bases = definition_info.get('bases', []); bases_str = f"(inherits: {', '.join(bases)})" if bases else ""
                description = f"Class `{name}` {bases_str} (lines {start_line}-{end_line}) in {filename}"
            change_verb = "New" if change == "new" else "Modified"
            findings['dependencies'].append(f"{change_verb} {description}. Review usage and potential impacts.")

        for definition_info in findings['python_definitions']:
            name = definition_info['name']; def_type = definition_info['type']; start_line = definition_info['start_line']
            end_line = definition_info['end_line']; args_list = definition_info.get('args', [])
            change = definition_info.get('change_type', 'changed'); args_str = ", ".join(args_list)
            change_desc = "New" if change == "new" else "Modified"; suggestion_text = ""
            if def_type == "function": suggestion_text = (f"{change_desc} function `{name}({args_str})` (lines {start_line}-{end_line}) detected. Recommend tests for logic, args, outcomes.")
            elif def_type == "method": suggestion_text = (f"{change_desc} method `{name}({args_str})` (lines {start_line}-{end_line}) detected. Recommend tests for changes, class state, inputs.")
            elif def_type == "class": suggestion_text = (f"{change_desc} class `{name}` (lines {start_line}-{end_line}) detected. Recommend test suite for constructor, methods, state.")
            if suggestion_text: findings['tests_suggestions'].append(suggestion_text)

    if ANALYSIS_PYTHON_TEST_STUB_GEN in analyses_to_run:
        for definition_info in findings.get('python_definitions', []): # Use correlated definitions
            if definition_info.get('change_type') == 'new':
                def_name = definition_info['name']; def_type = definition_info['type']
                original_module_path = filename; test_filename_suggestion = ""
                if original_module_path.startswith("src/"): test_filename_suggestion = original_module_path.replace("src/", "tests/test_", 1)
                elif original_module_path.startswith("./src/"): test_filename_suggestion = original_module_path.replace("./src/", "tests/test_", 1)
                elif "/" in original_module_path:
                    parts = original_module_path.split('/'); parts[-1] = "test_" + parts[-1]
                    test_filename_suggestion = "tests/" + "/".join(parts)
                else: test_filename_suggestion = "tests/test_" + original_module_path
                if not test_filename_suggestion.endswith(".py"):
                    base, _ = os.path.splitext(test_filename_suggestion); test_filename_suggestion = base + ".py"
                import_path_suggestion = original_module_path
                if import_path_suggestion.endswith(".py"): import_path_suggestion = import_path_suggestion[:-3]
                import_path_suggestion = import_path_suggestion.replace('/', '.')
                if import_path_suggestion.startswith("src."): import_path_suggestion = import_path_suggestion[4:]
                stub_code = ""
                if def_type == "function":
                    class_name = f"Test{def_name.capitalize()}"
                    stub_code = f"import unittest\n# TODO: Adjust import path if necessary: from {import_path_suggestion} import {def_name}\n\nclass {class_name}(unittest.TestCase):\n    def test_{def_name}_basic(self):\n        # TODO: Implement test\n        self.fail(\"Test not implemented for {def_name}\")\n\nif __name__ == '__main__':\n    unittest.main()"
                elif def_type == "class":
                    class_name = f"Test{def_name.capitalize()}"
                    stub_code = f"import unittest\n# TODO: Adjust import path if necessary: from {import_path_suggestion} import {def_name}\n\nclass {class_name}(unittest.TestCase):\n    def setUp(self):\n        # TODO: Set up instance: self.instance = {def_name}(...)\n        pass\n    def test_constructor(self):\n        # TODO: Test constructor\n        self.fail(\"Constructor test not implemented for {def_name}\")\n\nif __name__ == '__main__':\n    unittest.main()"
                if stub_code:
                    findings['python_test_stubs'].append({
                        'target_definition_name': def_name, 'target_definition_type': def_type,
                        'suggested_test_filename': test_filename_suggestion, 'stub_code': stub_code.strip()
                    })
        if not findings['python_test_stubs'] and findings.get('python_definitions'): # AST ran, defs exist, but none were new
             findings['impacts'].append(f"Python test stub generation: No new functions/classes found in {filename} for stubbing.")
        elif not findings.get('python_definitions') and ANALYSIS_PYTHON_AST in analyses_to_run: # AST ran but found no defs at all
             findings['impacts'].append(f"Python test stub generation: AST analysis found no definitions in {filename} for stubbing.")


    if not findings['tests_suggestions']: # Final fallback for test suggestions
        if changed_line_info:
            findings['tests_suggestions'].append(f"Changes detected in {filename} (hunks: {len(changed_line_info)}). Consider specific unit tests for modified logic based on patch.")
        elif file_status == 'added' and file_content and not definitions_from_ast and ANALYSIS_PYTHON_AST in analyses_to_run :
             findings['tests_suggestions'].append(f"{filename} was added and contains executable code but no definitions found by AST. Ensure appropriate tests.")
        elif findings['linting_issues'] and ANALYSIS_FLAKE8 in analyses_to_run:
            findings['tests_suggestions'].append(f"Review linting issues for {filename} and ensure test coverage.")
        elif file_content :
             findings['tests_suggestions'].append(f"Generic reminder: Ensure adequate test coverage for changes in {filename}.")
        elif not file_content and patch_text:
             findings['tests_suggestions'].append(f"Full content not analyzed for {filename}. Review patch changes and ensure test coverage.")
        else:
            findings['tests_suggestions'].append(f"No content or patch data for {filename} to provide specific test suggestions.")
    return findings

def _analyze_java_file(file_info: Dict[str, Any], pr_data: Dict[str, Any], analyses_to_run: List[str]) -> Dict[str, Any]:
    filename = file_info.get('filename')
    findings = {
        'file_path': filename, 'language': 'java', 'impacts': [],
        'dependencies': [], 'tests_suggestions': [], 'security_issues': [],
        'linting_issues': [], 'raw_analysis_data': {}
    }
    owner = pr_data.get('owner'); repo = pr_data.get('repo'); head_sha = pr_data.get('head_sha')
    file_content = None
    if owner and repo and head_sha and filename:
        api_headers = {"Accept": "application/vnd.github.v3+json"}
        file_content = get_file_content_at_ref(owner, repo, filename, head_sha, api_headers)
    else:
        findings['impacts'].append(f"Insufficient data to fetch full content for {filename}.")

    # This is the primary message if content fetching fails for Java.
    if not file_content:
        findings['impacts'].append(f"Java file {filename} changed, but full content not fetched for Checkstyle analysis (using patch for other checks if available).")

    if file_content and ANALYSIS_JAVA_PARSER in analyses_to_run:
        findings['impacts'].append(f"Java parsing (javalang) run for {filename} (placeholder - no actual parsing yet).")
    elif ANALYSIS_JAVA_PARSER not in analyses_to_run:
         findings['impacts'].append(f"Java parsing (javalang) skipped for {filename}.")
    # If content fetch failed but Java parsing was requested, the earlier "not fetched" message covers it.


    if file_content and ANALYSIS_JAVA_CHECKSTYLE in analyses_to_run:
        tmp_file_path = ""
        checkstyle_jar_cmd = os.getenv("CHECKSTYLE_JAR", "checkstyle.jar")
        config_file_path = DEFAULT_CHECKSTYLE_CONFIG
        if not os.path.exists(config_file_path):
            findings['impacts'].append(f"Checkstyle config not found: {config_file_path}")
        else:
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False, encoding='utf-8') as tmp_file:
                    tmp_file.write(file_content); tmp_file_path = tmp_file.name
                cmd = ['java', '-jar', checkstyle_jar_cmd, '-c', config_file_path, '-f', 'xml', tmp_file_path]
                process = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')
                stderr_output = process.stderr.strip()
                if stderr_output:
                    print(f"Checkstyle stderr for {filename} (temp {tmp_file_path}): {stderr_output}")
                    if "Exception" in stderr_output or "Error" in stderr_output or "Could not" in stderr_output:
                        findings['impacts'].append(f"Checkstyle operational error for {filename} (see console logs).")
                if process.stdout: findings['linting_issues'] = _parse_checkstyle_xml_output(process.stdout, filename)
                elif not stderr_output: findings['linting_issues'] = []
            except FileNotFoundError:
                findings['impacts'].append(f"Checkstyle execution failed for {filename}. Ensure Java and '{checkstyle_jar_cmd}' are accessible. Set CHECKSTYLE_JAR or ensure it's in PATH.")
            except Exception as e:
                findings['impacts'].append(f"Error running Checkstyle on {filename}: {str(e)}")
            finally:
                if tmp_file_path and os.path.exists(tmp_file_path): os.remove(tmp_file_path)
    elif ANALYSIS_JAVA_CHECKSTYLE not in analyses_to_run:
        findings['impacts'].append(f"Checkstyle linting skipped for {filename}.")
    elif not file_content and ANALYSIS_JAVA_CHECKSTYLE in analyses_to_run: # Checkstyle on, but no content
         findings['impacts'].append(f"Checkstyle linting skipped for {filename} because full content was not available.")


    patch_text = file_info.get('patch')
    if patch_text:
        # Add general "modified" impact only if not added by other more specific messages related to content analysis.
        if not file_content: # If content wasn't fetched, this is the primary "modified" indicator.
            findings['impacts'].append(f"Java file {filename} was modified (Status: {file_info.get('status', 'N/A')}, patch available).")

        current_test_suggestions = findings.get('tests_suggestions', [])
        if not current_test_suggestions:
            current_test_suggestions.append(f"Review changes in {filename} (patch available) and consider specific JUnit tests.")
        findings['tests_suggestions'] = current_test_suggestions

        if not findings.get('dependencies'):
            findings['dependencies'].append(f"Manual check: Review {filename} (patch available) for impacts on dependents.")

        if ANALYSIS_SECURITY_KEYWORD_SCAN in analyses_to_run:
            for keyword in RUDIMENTARY_SECURITY_KEYWORDS:
                if keyword in patch_text:
                    findings['security_issues'].append(f"Potential security keyword '{keyword}' found in changed lines.")
    elif not findings['impacts'] and not file_content: # No patch, no content from fetch
        findings['impacts'].append(f"Java file {filename} (Status: {file_info.get('status', 'N/A')}) processed (no patch data, no content fetched).")

    if not findings['tests_suggestions']: # Final fallback for Java
        if findings['linting_issues'] and ANALYSIS_JAVA_CHECKSTYLE in analyses_to_run:
            findings['tests_suggestions'].append(f"Review linting issues for {filename} and ensure test coverage.")
        elif file_content: # Content was processed (e.g. by parser, or just existed)
            findings['tests_suggestions'].append(f"Generic reminder: Ensure adequate JUnit test coverage for {filename}.")
        else: # No content, no patch, no linting
            findings['tests_suggestions'].append(f"No content or patch data for {filename}. Review file status and ensure coverage.")
    return findings

def _analyze_other_file(file_info: Dict[str, Any], pr_data: Dict[str, Any]) -> Dict[str, Any]:
    findings = {
        'file_path': file_info.get('filename'), 'language': 'other',
        'impacts': [f"Non-code file changed: {file_info['filename']} (Status: {file_info.get('status', 'N/A')})"],
        'dependencies': [], 'tests_suggestions': [], 'security_issues': [],
        'linting_issues': [], 'raw_analysis_data': {}
    }
    return findings

def analyze_code_changes(pr_data: Dict[str, Any], analyses_to_run: List[str]) -> Dict[str, Any]:
    if not pr_data or 'files_changed' not in pr_data:
        print("Error: Invalid PR data provided for analysis in analyze_code_changes.")
        return {
            'overall_summary': {'reuse_suggestions': [], 'solid_violations': [], 'general_security_reminders': []},
            'file_specific_findings': []
        }
    print(f"Analyzing PR (multi-language): {pr_data.get('title', 'N/A')} with active analyses: {analyses_to_run}")
    file_specific_findings_list = []
    for file_info in pr_data.get('files_changed', []):
        filename = file_info.get('filename', '')
        if not filename: continue
        if filename.endswith('.py'):
            findings = _analyze_python_file(file_info, pr_data, analyses_to_run)
        elif filename.endswith('.java'):
            findings = _analyze_java_file(file_info, pr_data, analyses_to_run)
        else:
            findings = _analyze_other_file(file_info, pr_data)
        file_specific_findings_list.append(findings)

    overall_reuse_suggestions = []
    if len(pr_data.get('files_changed', [])) > 1:
        overall_reuse_suggestions.append("Consider if there are common patterns across the changed files that could be abstracted globally.")
    overall_solid_violations = ["Reminder: Review all code changes for adherence to SOLID principles."]
    general_security_reminders = []
    if ANALYSIS_SECURITY_KEYWORD_SCAN in analyses_to_run and \
       any(f_item.get('language') in ['python', 'java'] for f_item in file_specific_findings_list):
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
            {'filename': 'src/module_a/file1.py', 'status': 'added', 'patch': "def new_func():\n  pass\n\nclass NewClass:\n  pass"},
        ]
    }
    test_analyses = ALL_ANALYSES
    analysis_results_py = analyze_code_changes(mock_pr_data_py, test_analyses)
    # ... (rest of main block for printing) ...
