# src/code_analyzer.py

import ast
import re
import javalang
from javalang.tree import CompilationUnit, PackageDeclaration, Import, \
                          ClassDeclaration, InterfaceDeclaration, EnumDeclaration, \
                          MethodDeclaration, FieldDeclaration, ConstructorDeclaration, \
                          Annotation, FormalParameter, TypeArgument, ReferenceType
import subprocess
import tempfile
import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional # Added Optional
import json # Added for loading security keywords

ANALYSIS_PYTHON_AST = "python_ast"; ANALYSIS_FLAKE8 = "flake8"; ANALYSIS_JAVA_CHECKSTYLE = "checkstyle"; ANALYSIS_JAVA_PARSER = "java_parser"; ANALYSIS_SECURITY_KEYWORD_SCAN = "security_scan"; ANALYSIS_PYTHON_TEST_STUB_GEN = "python_test_stubs"; ANALYSIS_MAVEN_POM = "maven_pom_analysis"; ANALYSIS_JAVA_TEST_STUB_GEN = "java_test_stubs"
ALL_ANALYSES = [ANALYSIS_PYTHON_AST, ANALYSIS_FLAKE8, ANALYSIS_JAVA_CHECKSTYLE, ANALYSIS_JAVA_PARSER, ANALYSIS_SECURITY_KEYWORD_SCAN, ANALYSIS_PYTHON_TEST_STUB_GEN, ANALYSIS_MAVEN_POM, ANALYSIS_JAVA_TEST_STUB_GEN]
DEFAULT_ANALYSES_TO_RUN = [ANALYSIS_PYTHON_AST, ANALYSIS_FLAKE8, ANALYSIS_JAVA_CHECKSTYLE, ANALYSIS_SECURITY_KEYWORD_SCAN, ANALYSIS_JAVA_PARSER, ANALYSIS_MAVEN_POM]
# RUDIMENTARY_SECURITY_KEYWORDS will be replaced by loaded config

SECURITY_SCAN_CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'config', 'security_keywords.json'))
SECURITY_SCAN_CONFIG: Dict[str, Any] = {"keywords": [], "patterns": []} # Default empty config

def _load_security_scan_config():
    """Loads security keywords and regex patterns from the JSON config file."""
    global SECURITY_SCAN_CONFIG
    try:
        with open(SECURITY_SCAN_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            SECURITY_SCAN_CONFIG["keywords"] = config_data.get("keywords", [])

            loaded_patterns = []
            for p_info in config_data.get("patterns", []):
                try:
                    # Compile regex patterns for efficiency and store with their names
                    loaded_patterns.append({
                        "name": p_info.get("name", "Unnamed Pattern"),
                        "pattern": re.compile(p_info.get("pattern"))
                    })
                except re.error as e:
                    print(f"Warning: Failed to compile security regex pattern '{p_info.get('name')}': {e}")
                except Exception as e:
                    print(f"Warning: Unexpected error processing pattern '{p_info.get('name')}': {e}")
            SECURITY_SCAN_CONFIG["patterns"] = loaded_patterns

            if not SECURITY_SCAN_CONFIG["keywords"] and not SECURITY_SCAN_CONFIG["patterns"]:
                print(f"Warning: Security scan configuration loaded from {SECURITY_SCAN_CONFIG_PATH}, but it's empty or invalid.")
            else:
                print(f"Successfully loaded {len(SECURITY_SCAN_CONFIG['keywords'])} keywords and {len(SECURITY_SCAN_CONFIG['patterns'])} patterns for security scan.")

    except FileNotFoundError:
        print(f"Warning: Security keyword config file not found at {SECURITY_SCAN_CONFIG_PATH}. Security scan will be limited.")
        SECURITY_SCAN_CONFIG = {"keywords": [], "patterns": []} # Ensure it's reset
    except json.JSONDecodeError as e:
        print(f"Warning: Error decoding JSON from {SECURITY_SCAN_CONFIG_PATH}: {e}. Security scan will be limited.")
        SECURITY_SCAN_CONFIG = {"keywords": [], "patterns": []} # Ensure it's reset
    except Exception as e:
        print(f"Warning: An unexpected error occurred while loading security scan config: {e}")
        SECURITY_SCAN_CONFIG = {"keywords": [], "patterns": []}

_load_security_scan_config() # Load config when module is loaded

if __package__ is None or __package__ == '':
    import sys; from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path: sys.path.append(str(project_root))
    from src.pr_parser import get_file_content_at_ref
else:
    from .pr_parser import get_file_content_at_ref
DEFAULT_CHECKSTYLE_CONFIG = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'config', 'google_checks.xml'))

def _get_changed_line_ranges_from_patch(patch_text_local: str) -> List[Tuple[int, int]]:
    ranges_local = []
    if patch_text_local:
        for line_local in patch_text_local.splitlines():
            if line_local.startswith("@@"):
                match_local = re.search(r"\+([0-9]+)(?:,([0-9]+))?", line_local)
                if match_local:
                    start_line = int(match_local.group(1)); length = int(match_local.group(2) or 1)
                    if length > 0: ranges_local.append((start_line, length))
    return ranges_local

def _parse_flake8_output(output_str: str, original_filename: str) -> List[Dict[str, Any]]:
    linting_issues = []
    for line in output_str.splitlines():
        match = re.match(r"^[^:]+:([0-9]+):([0-9]+): ([A-Z][0-9]+) (.*)$", line)
        if match: linting_issues.append({"file": original_filename, "line": int(match.group(1)), "column": int(match.group(2)), "code": match.group(3), "message": match.group(4).strip()})
        elif line.strip(): linting_issues.append({"file": original_filename, "line": 0, "column": 0, "code": "FLAKE8_PARSE_ERROR", "message": f"Unparseable Flake8 output line: {line.strip()}"})
    return linting_issues

def _parse_checkstyle_xml_output(xml_str: str, original_filename: str) -> List[Dict[str, Any]]:
    linting_issues = [];
    if not xml_str: return linting_issues
    try:
        root = ET.fromstring(xml_str)
        for file_node in root.findall('file'):
            for error_node in file_node.findall('error'):
                try: linting_issues.append({"file": original_filename, "line": int(error_node.get('line', '0')), "column": int(error_node.get('column', '0')), "code": error_node.get('source', '').split('.')[-1] or 'CheckstyleError', "message": error_node.get('message', 'No message'), "severity": error_node.get('severity', 'info')})
                except ValueError as ve: linting_issues.append({"file": original_filename, "line": 0, "column": 0, "code": "PARSE_ERROR", "message": f"Error parsing Checkstyle error node: {ve}. Node: {ET.tostring(error_node, encoding='unicode')}"})
    except ET.ParseError as e: linting_issues.append({"file": original_filename, "line": 0, "column": 0, "code": "XML_PARSE_ERROR", "message": f"Failed to parse Checkstyle XML output: {e}"})
    return linting_issues

def _format_javalang_type_node(type_node) -> str:
    if type_node is None: return "void"
    name_str = ""
    if isinstance(type_node, javalang.tree.BasicType):
        name_str = type_node.name
    elif isinstance(type_node, javalang.tree.ReferenceType):
        # Corrected logic for ReferenceType name construction
        name_parts = []
        current = type_node
        while current:
            name_parts.append(current.name)
            current = getattr(current, 'sub_type', None)
        name_str = ".".join(name_parts)

        if type_node.arguments:
            args = [_format_javalang_type_node(arg.type) for arg in type_node.arguments if hasattr(arg, 'type') and arg.type]
            if args: name_str += f"<{', '.join(args)}>"
    elif hasattr(type_node, 'name'): name_str = str(type_node.name)
    else: name_str = "unknown_type"

    if hasattr(type_node, 'dimensions') and type_node.dimensions:
        name_str += "[]" * len(type_node.dimensions)
    return name_str

def _analyze_python_file(file_info: Dict[str, Any], pr_data: Dict[str, Any], analyses_to_run: List[str], flake8_options_str: Optional[str] = None) -> Dict[str, Any]:
    filename = file_info.get('filename')
    findings = {'file_path': filename, 'language': 'python', 'impacts': [], 'dependencies': [], 'tests_suggestions': [], 'security_issues': [], 'linting_issues': [], 'python_definitions': [], 'python_test_stubs': [], 'raw_analysis_data': {}}
    owner = pr_data.get('owner'); repo = pr_data.get('repo'); head_sha = pr_data.get('head_sha')
    file_content = None
    if owner and repo and head_sha and filename:
        api_headers = {"Accept": "application/vnd.github.v3+json"}; file_content = get_file_content_at_ref(owner, repo, filename, head_sha, api_headers)
    else: findings['impacts'].append(f"Insufficient data to fetch full content for {filename}.")
    if not file_content and (ANALYSIS_PYTHON_AST in analyses_to_run or ANALYSIS_FLAKE8 in analyses_to_run):
        findings['impacts'].append(f"Python file {filename} changed, but full content not fetched for analysis (using patch for other checks if available).")
    definitions_from_ast = []
    if file_content and ANALYSIS_PYTHON_AST in analyses_to_run:
        try:
            tree = ast.parse(file_content, filename=filename)
            for node in ast.walk(tree):
                definition_info = None
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [arg.arg for arg in node.args.args]; end_line = getattr(node, 'end_lineno', node.lineno); def_type = "function";
                    if args and args[0] in ['self', 'cls']: def_type = "method"
                    definition_info = {"name": node.name, "type": def_type, "start_line": node.lineno, "end_line": end_line if end_line is not None else node.lineno, "args": args, "decorators": [dec.id for dec in node.decorator_list if isinstance(dec, ast.Name)] + [ast.dump(dec) for dec in node.decorator_list if not isinstance(dec, ast.Name)]}
                elif isinstance(node, ast.ClassDef):
                    definition_info = {"name": node.name, "type": "class", "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', node.lineno), "methods": [], "bases": [base.id for base in node.bases if isinstance(base, ast.Name)], "decorators": [dec.id for dec in node.decorator_list if isinstance(dec, ast.Name)] + [ast.dump(dec) for dec in node.decorator_list if not isinstance(dec, ast.Name)]}
                if definition_info: definitions_from_ast.append(definition_info)
            if not definitions_from_ast: findings['impacts'].append(f"Python AST analysis run on {filename}, but no class/function definitions identified.")
        except SyntaxError as e: findings['impacts'].append(f"Python AST SyntaxError in {filename}: {e.msg} (line {e.lineno}).")
        except Exception as e: findings['impacts'].append(f"Python AST parsing error in {filename}: {str(e)}.")
    elif ANALYSIS_PYTHON_AST not in analyses_to_run: findings['impacts'].append(f"Python AST analysis skipped for {filename}.")
    if file_content and ANALYSIS_FLAKE8 in analyses_to_run:
        tmp_file_path = ""
        try:
            flake8_cmd = ['flake8']
            if flake8_options_str:
                # Simple split by space. For more complex parsing (e.g., quotes), shlex.split might be needed.
                custom_options = flake8_options_str.split()
                flake8_cmd.extend(custom_options)
                findings['impacts'].append(f"Using custom Flake8 options for {filename}: {flake8_options_str}")

            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name

            flake8_cmd.append(tmp_file_path) # Add file to be linted as the last argument

            process = subprocess.run(flake8_cmd, capture_output=True, text=True, check=False, encoding='utf-8')
            findings['linting_issues'] = _parse_flake8_output(process.stdout, filename)
            if process.stderr:
                # Flake8 sometimes outputs version info or other non-error messages to stderr
                # We might want to log this more selectively or if exit code indicates an error
                # For now, just printing it as before.
                print(f"Flake8 stderr for {filename} (temp {tmp_file_path}): {process.stderr.strip()}")
        except FileNotFoundError: findings['impacts'].append(f"Flake8 command not found for {filename}.")
        except Exception as e: findings['impacts'].append(f"Error running Flake8 on {filename}: {str(e)}")
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path): os.remove(tmp_file_path)
    elif ANALYSIS_FLAKE8 not in analyses_to_run: findings['impacts'].append(f"Flake8 linting skipped for {filename}.")
    elif not file_content and ANALYSIS_FLAKE8 in analyses_to_run : findings['impacts'].append(f"Flake8 linting skipped for {filename} because full content was not available.")
    patch_text = file_info.get('patch'); changed_line_info = []; file_status = file_info.get('status', 'modified')
    if patch_text:
        changed_line_info = _get_changed_line_ranges_from_patch(patch_text)
        if not file_content and not any("full content not fetched" in imp for imp in findings['impacts']): findings['impacts'].append(f"Python file {filename} was modified (Status: {file_info.get('status', 'N/A')}, patch available but content fetch failed).")
        if ANALYSIS_SECURITY_KEYWORD_SCAN in analyses_to_run:
            findings['security_issues'] = _perform_security_scan(patch_text)
    elif not findings['impacts'] : findings['impacts'].append(f"Python file {filename} (Status: {file_info.get('status', 'N/A')}) processed (no patch data).")
    if ANALYSIS_PYTHON_AST in analyses_to_run and definitions_from_ast:
        modified_definitions_count = 0; current_impacts = [imp for imp in findings['impacts'] if not imp.startswith("AST parsed") and not imp.startswith("Python AST SyntaxError") and not imp.startswith("Python AST parsing error")]
        for definition in definitions_from_ast:
            def_start = definition['start_line']; def_end = definition['end_line']; change_type = None
            if file_status == 'added': change_type = 'new'
            elif changed_line_info:
                for hunk_start, hunk_length in changed_line_info:
                    hunk_end = hunk_start + hunk_length -1
                    if max(def_start, hunk_start) <= min(def_end, hunk_end): change_type = 'modified'; break
            if change_type: definition['change_type'] = change_type; findings['python_definitions'].append(definition); modified_definitions_count +=1
        findings['impacts'] = current_impacts
        if modified_definitions_count > 0: findings['impacts'].append(f"Identified {modified_definitions_count} new/modified Python definitions in {filename} within changed code sections.")
        elif definitions_from_ast: findings['impacts'].append(f"AST parsed {len(definitions_from_ast)} definitions in {filename}, but none appear directly in changed code lines.")
        findings['dependencies'] = []
        for definition_info in findings['python_definitions']:
            name = definition_info['name']; def_type = definition_info['type']; start_line = definition_info['start_line']; end_line = definition_info['end_line']; args_list = definition_info.get('args', []); change = definition_info.get('change_type', 'changed'); args_str = ", ".join(args_list); description = ""
            if def_type == "method": description = f"Method `{name}({args_str})` (lines {start_line}-{end_line}) in {filename}"
            elif def_type == "function": description = f"Function `{name}({args_str})` (lines {start_line}-{end_line}) in {filename}"
            elif def_type == "class": bases = definition_info.get('bases', []); bases_str = f"(inherits: {', '.join(bases)})" if bases else ""; description = f"Class `{name}` {bases_str} (lines {start_line}-{end_line}) in {filename}"
            change_verb = "New" if change == "new" else "Modified"; findings['dependencies'].append(f"{change_verb} {description}. Review usage and potential impacts.")
        findings['tests_suggestions'] = []
        for definition_info in findings['python_definitions']:
            name = definition_info['name']; def_type = definition_info['type']; start_line = definition_info['start_line']; end_line = definition_info['end_line']; args_list = definition_info.get('args', []); change = definition_info.get('change_type', 'changed'); args_str = ", ".join(args_list); change_desc = "New" if change == "new" else "Modified"; suggestion_text = ""
            if def_type == "function": suggestion_text = (f"{change_desc} function `{name}({args_str})` (lines {start_line}-{end_line}) detected. Recommend tests for logic, args, outcomes.")
            elif def_type == "method": suggestion_text = (f"{change_desc} method `{name}({args_str})` (lines {start_line}-{end_line}) detected. Recommend tests for changes, class state, inputs.")
            elif def_type == "class": suggestion_text = (f"{change_desc} class `{name}` (lines {start_line}-{end_line}) detected. Recommend test suite for constructor, methods, state.")
            if suggestion_text: findings['tests_suggestions'].append(suggestion_text)
    if ANALYSIS_PYTHON_TEST_STUB_GEN in analyses_to_run:
        stubs_generated_count = 0
        for definition_info in findings.get('python_definitions', []):
            if definition_info.get('change_type') == 'new':
                def_name = definition_info['name']; def_type = definition_info['type']; original_module_path = filename; test_filename_suggestion = "";
                if original_module_path.startswith("src/"): test_filename_suggestion = original_module_path.replace("src/", "tests/test_", 1)
                elif original_module_path.startswith("./src/"): test_filename_suggestion = original_module_path.replace("./src/", "tests/test_", 1)
                elif "/" in original_module_path: parts = original_module_path.split('/'); parts[-1] = "test_" + parts[-1]; test_filename_suggestion = "tests/" + "/".join(parts)
                else: test_filename_suggestion = "tests/test_" + original_module_path
                if not test_filename_suggestion.endswith(".py"): base, _ = os.path.splitext(test_filename_suggestion); test_filename_suggestion = base + ".py"
                import_path_suggestion = original_module_path
                if import_path_suggestion.endswith(".py"): import_path_suggestion = import_path_suggestion[:-3]
                import_path_suggestion = import_path_suggestion.replace('/', '.');
                if import_path_suggestion.startswith("src."): import_path_suggestion = import_path_suggestion[4:]
                stub_code = ""
                args_list = definition_info.get('args', []) # Get args for functions/methods

                # For functions, 'self' or 'cls' should not be in args_list if it's a true standalone function.
                # For methods identified by AST (if we were to stub them individually), they would be.
                # Current logic: 'function' type means standalone, 'method' is identified by 'self'/'cls' in args.
                # The stub generator is primarily for *new* top-level functions or *new* classes.

                method_args_for_signature = ""
                if def_type == "function": # Standalone function
                    method_args_for_signature = ", ".join(args_list)
                # If it were a method of a class, args_list would include 'self' or 'cls'.
                # For test method signature, we don't need 'self'.

                if def_type == "function":
                    class_name = f"Test{def_name.capitalize()}"
                    # Args for calling the function in the test:
                    call_args_str = ", ".join(args_list) if args_list else ""
                    stub_code = f"""import unittest
# TODO: Adjust import path if necessary
# from {import_path_suggestion} import {def_name}

class {class_name}(unittest.TestCase):
    def test_{def_name}_basic(self):
        # TODO: Define test cases for {def_name}({call_args_str})
        # Example: self.assertEqual({def_name}(input_value), expected_output)
        raise NotImplementedError("Test not implemented for {def_name}")

if __name__ == '__main__':
    unittest.main()"""
                elif def_type == "class":
                    class_name = f"Test{def_name.capitalize()}"
                    # Methods within the class are not individually processed here for stubs by current logic,
                    # only the class itself.
                    stub_code = f"""import unittest
# TODO: Adjust import path if necessary
# from {import_path_suggestion} import {def_name}

class {class_name}(unittest.TestCase):
    def setUp(self):
        # TODO: Set up an instance of {def_name} if needed for tests
        # Example: self.instance = {def_name}()
        raise NotImplementedError("setUp not implemented for testing {def_name}")

    def test_constructor(self):
        # TODO: Test the constructor of {def_name}
        # Example: instance = {def_name}(param1, param2)
        #          self.assertIsNotNone(instance)
        raise NotImplementedError("Constructor test not implemented for {def_name}")

    # TODO: Add test methods for other public methods of {def_name}
    # Example:
    # def test_some_method(self):
    #     instance = {def_name}() # or use self.instance from setUp
    #     # self.assertEqual(instance.some_method(params), expected_output)
    #     raise NotImplementedError("Test for some_method of {def_name} not implemented")

if __name__ == '__main__':
    unittest.main()"""
                if stub_code: findings['python_test_stubs'].append({'target_definition_name': def_name, 'target_definition_type': def_type, 'suggested_test_filename': test_filename_suggestion, 'stub_code': stub_code.strip() }); stubs_generated_count+=1
        if stubs_generated_count == 0 and findings.get('python_definitions') and ANALYSIS_PYTHON_AST in analyses_to_run : findings['impacts'].append(f"Python test stub generation: No new functions/classes suitable for stubbing found in {filename}.")
        elif not findings.get('python_definitions') and ANALYSIS_PYTHON_AST in analyses_to_run : findings['impacts'].append(f"Python test stub generation: AST analysis found no definitions in {filename} for stubbing.")
        elif ANALYSIS_PYTHON_AST not in analyses_to_run: findings['impacts'].append(f"Python test stub generation skipped as AST analysis (source of definitions) was not run for {filename}.")
    if not findings['tests_suggestions']:
        if changed_line_info: findings['tests_suggestions'].append(f"Changes detected in {filename} (hunks: {len(changed_line_info)}). Consider specific unit tests for modified logic based on patch.")
        elif file_status == 'added' and file_content and not definitions_from_ast and ANALYSIS_PYTHON_AST in analyses_to_run : findings['tests_suggestions'].append(f"{filename} was added and contains executable code but no definitions found by AST. Ensure appropriate tests.")
        elif findings['linting_issues'] and ANALYSIS_FLAKE8 in analyses_to_run: findings['tests_suggestions'].append(f"Review linting issues for {filename} and ensure test coverage.")
        elif file_content : findings['tests_suggestions'].append(f"Generic reminder: Ensure adequate test coverage for changes in {filename}.")
        elif not file_content and patch_text: findings['tests_suggestions'].append(f"Full content not analyzed for {filename}. Review patch changes and ensure test coverage.")
        else: findings['tests_suggestions'].append(f"No content or patch data for {filename} to provide specific test suggestions.")
    return findings

def _analyze_java_file(file_info: Dict[str, Any], pr_data: Dict[str, Any], analyses_to_run: List[str], checkstyle_config_path: Optional[str] = None) -> Dict[str, Any]:
    filename = file_info.get('filename')
    findings = {'file_path': filename, 'language': 'java', 'impacts': [], 'dependencies': [], 'tests_suggestions': [], 'security_issues': [], 'linting_issues': [], 'java_definitions': [], 'java_test_stubs': [], 'raw_analysis_data': {}}
    owner = pr_data.get('owner'); repo = pr_data.get('repo'); head_sha = pr_data.get('head_sha')
    file_content = None
    if owner and repo and head_sha and filename:
        api_headers = {"Accept": "application/vnd.github.v3+json"}; file_content = get_file_content_at_ref(owner, repo, filename, head_sha, api_headers)
    else: findings['impacts'].append(f"Insufficient data to fetch full content for {filename}.")

    if not file_content and (ANALYSIS_JAVA_PARSER in analyses_to_run or ANALYSIS_JAVA_CHECKSTYLE in analyses_to_run):
        findings['impacts'].append(f"Java file {filename} changed, but full content not fetched for analysis (using patch for other checks if available).")

    all_definitions_from_javalang = []
    if file_content and ANALYSIS_JAVA_PARSER in analyses_to_run:
        try:
            tree = javalang.parse.parse(file_content)
            if tree.package: all_definitions_from_javalang.append({"type": "package", "name": tree.package.name, "start_line": tree.package.position.line if tree.package.position else 0})
            for imp_node in tree.imports: all_definitions_from_javalang.append({"type": "import", "name": imp_node.path, "static": imp_node.static, "wildcard": imp_node.wildcard, "start_line": imp_node.position.line if imp_node.position else 0})
            for type_decl in tree.types:
                if hasattr(type_decl, 'name') and hasattr(type_decl, 'position') and type_decl.position:
                    parent_class_modifiers = list(type_decl.modifiers) if isinstance(type_decl, (ClassDeclaration, InterfaceDeclaration, EnumDeclaration)) else []
                    class_info = {"type": type(type_decl).__name__, "name": type_decl.name, "start_line": type_decl.position.line, "modifiers": parent_class_modifiers, "methods": [], "fields": []}
                    if hasattr(type_decl, 'implements') and type_decl.implements: class_info['implements'] = [_format_javalang_type_node(impl) for impl in type_decl.implements]
                    if hasattr(type_decl, 'extends') and type_decl.extends:
                        if isinstance(type_decl.extends, list): class_info['extends'] = [_format_javalang_type_node(ext) for ext in type_decl.extends]
                        else: class_info['extends'] = _format_javalang_type_node(type_decl.extends)

                    if hasattr(type_decl, 'body') and type_decl.body:
                        # Estimate end_line by finding the maximum line number in the body
                        all_lines = [type_decl.position.line] if hasattr(type_decl, 'position') and type_decl.position else []
                        if hasattr(type_decl, 'body') and type_decl.body:
                            for member in type_decl.body:
                                if hasattr(member, 'position') and member.position:
                                    all_lines.append(member.position.line)
                        if all_lines:
                            class_info['end_line'] = max(all_lines)

                        for member in type_decl.body:
                            member_start_line = member.position.line if hasattr(member, 'position') and member.position else class_info['start_line']
                            if isinstance(member, (MethodDeclaration, ConstructorDeclaration)):
                                params = [];
                                if member.parameters:
                                    for p in member.parameters: params.append((_format_javalang_type_node(p.type), p.name))
                                return_type_name = "void"
                                if isinstance(member, MethodDeclaration): return_type_name = _format_javalang_type_node(member.return_type)
                                member_type = "method" if isinstance(member, MethodDeclaration) else "constructor"
                                class_info['methods'].append({"type": member_type, "name": member.name, "start_line": member_start_line, "parameters": params, "return_type": return_type_name, "modifiers": list(member.modifiers), "parent_class_modifiers": parent_class_modifiers})
                            elif isinstance(member, FieldDeclaration):
                                field_type_name = _format_javalang_type_node(member.type)
                                for decl in member.declarators: class_info['fields'].append({"type": "field", "name": decl.name, "field_type": field_type_name, "start_line": member_start_line, "modifiers": list(member.modifiers)})
                            elif isinstance(member, (ClassDeclaration, InterfaceDeclaration, EnumDeclaration)): class_info['methods'].append({"type": "inner_" + type(member).__name__.lower().replace("declaration",""), "name": member.name, "start_line": member_start_line})
                    all_definitions_from_javalang.append(class_info)
            if not all_definitions_from_javalang: findings['impacts'].append(f"Java parsing (javalang) run on {filename}, but no structural elements found.")
        except javalang.parser.JavaSyntaxError as e: findings['impacts'].append(f"Could not parse Java file {filename} with javalang: {e.description} at line {e.at.line if e.at else 'unknown'}")
        except Exception as e: findings['impacts'].append(f"Unexpected error during javalang parsing of {filename}: {str(e)}")
    elif ANALYSIS_JAVA_PARSER not in analyses_to_run: findings['impacts'].append(f"Java parsing (javalang) skipped for {filename}.")

    patch_text = file_info.get('patch'); changed_line_info = []; file_status = file_info.get('status', 'modified')
    if patch_text: changed_line_info = _get_changed_line_ranges_from_patch(patch_text)

    if ANALYSIS_JAVA_PARSER in analyses_to_run and all_definitions_from_javalang:
        identified_changed_definitions = []
        # Preserve existing impacts not related to javalang parsing success/failure messages
        current_impacts = [imp for imp in findings['impacts']
                           if not imp.startswith("Successfully parsed Java file") and \
                              not imp.startswith("Parsed Java file with javalang") and \
                              not imp.startswith("Could not parse Java file with javalang") and \
                              not imp.startswith("Unexpected error during javalang parsing")]

        for definition in all_definitions_from_javalang:
            change_type = None
            is_code_entity = definition['type'] not in ['package', 'import']
            def_start = definition.get('start_line', 0)

            if is_code_entity and def_start > 0 and ('name' in definition or definition.get('type') == 'ConstructorDeclaration'):
                def_end = definition.get('end_line', def_start)
                if file_status == 'added':
                    change_type = 'new'
                elif changed_line_info:
                    for hunk_start, hunk_length in changed_line_info:
                        hunk_end = hunk_start + hunk_length - 1
                        if max(def_start, hunk_start) <= min(def_end, hunk_end):
                            change_type = 'modified'
                            break
            if change_type:
                definition['change_type'] = change_type
                if definition['type'] in ['ClassDeclaration', 'InterfaceDeclaration', 'EnumDeclaration']:
                    for member_list_key in ['methods', 'fields']:
                        for member in definition.get(member_list_key, []):
                            member['change_type'] = change_type
                identified_changed_definitions.append(definition)
            elif not is_code_entity:
                identified_changed_definitions.append(definition)

        findings['java_definitions'] = identified_changed_definitions
        findings['impacts'] = current_impacts
        num_changed_identified = len([d for d in identified_changed_definitions if 'change_type' in d and d['type'] not in ['package', 'import']])
        num_total_parsed = len(all_definitions_from_javalang)
        if num_changed_identified > 0: findings['impacts'].append(f"Identified {num_changed_identified} new/modified Java code definitions in {filename} (out of {num_total_parsed} total structural elements parsed).")
        elif num_total_parsed > 0 and any(d['type'] not in ['package', 'import'] for d in all_definitions_from_javalang) : findings['impacts'].append(f"Parsed {num_total_parsed} Java structural elements in {filename}, but no code definitions appear directly in changed lines.")
        elif num_total_parsed > 0: findings['impacts'].append(f"Parsed {num_total_parsed} Java package/import statements from {filename}.")

        findings['dependencies'] = []; findings['tests_suggestions'] = []
        newly_added_imports = []
        if file_status == 'added':
            for def_info in findings.get('java_definitions', []):
                if def_info.get('type') == 'import': newly_added_imports.append(def_info.get('name'))
            if newly_added_imports: findings['dependencies'].append(f"Newly added file {filename} includes imports: {', '.join(newly_added_imports)}. Review necessity.")

        definitions_to_process_for_suggs = []
        for def_info in findings.get('java_definitions', []):
            if def_info.get('change_type'): definitions_to_process_for_suggs.append(def_info) # Top-level defs
            if def_info.get('type') in ['ClassDeclaration', 'InterfaceDeclaration', 'EnumDeclaration'] and def_info.get('change_type'):
                for member_list_key in ['methods', 'fields']: # Include members of new/modified top-level defs
                    for member in def_info.get(member_list_key, []):
                        member_detail = member.copy(); member_detail['change_type'] = def_info['change_type']
                        member_detail['parent_class_name'] = def_info['name']; member_detail['parent_class_modifiers'] = def_info.get('modifiers', [])
                        definitions_to_process_for_suggs.append(member_detail)

        for definition_info in definitions_to_process_for_suggs:
            change = definition_info.get('change_type');
            if not change: continue
            name = definition_info.get('name', 'N/A'); def_type_full = definition_info['type']; def_type_simple = def_type_full.replace("Declaration", "").lower()
            start_line = definition_info.get('start_line',0); modifiers = definition_info.get('modifiers', []); visibility = "package-private"
            if "public" in modifiers: visibility = "public";
            elif "private" in modifiers: visibility = "private";
            elif "protected" in modifiers: visibility = "protected"
            description = ""; change_verb = "New" if change == "new" else "Modified"; suggestion_text = ""
            parent_class_name_for_member = definition_info.get('parent_class_name', name)

            if def_type_full in ["ClassDeclaration", "InterfaceDeclaration", "EnumDeclaration"]:
                bases = definition_info.get('extends'); impls = definition_info.get('implements', []); heritage = ""
                if bases: heritage += f" extends {bases}" if not isinstance(bases, list) else f" extends {', '.join(bases)}"
                if impls: heritage += f" implements {', '.join(impls)}"
                description = f"{visibility} {def_type_simple} `{name}`{heritage} (declared line {start_line})"
                findings['dependencies'].append(f"{change_verb} {description} in {filename}. Review role and integration.")
                if not ("private" in modifiers or "protected" in modifiers): suggestion_text = (f"{change_verb} {visibility} {def_type_simple} `{name}` (line {start_line}) in {filename}. Review/add JUnit tests for public API, constructor(s), and key functionalities.")

            elif def_type_full == "method" or def_type_full == "constructor":
                params_list = definition_info.get('parameters', []); params_str = ", ".join([f"{p_type} {p_name}" for p_type, p_name in params_list])
                return_type_str = definition_info.get('return_type', 'void') if def_type_full == "method" else ""
                method_name_for_note = name if def_type_full == "method" else f"constructor for {parent_class_name_for_member}"
                description = f"{visibility} {return_type_str} {def_type_simple} `{method_name_for_note}({params_str})` (declared line {start_line})"
                findings['dependencies'].append(f"{change_verb} {description} in {filename}. Consider impact on callers.")
                parent_mods = definition_info.get('parent_class_modifiers', [])
                is_parent_public_or_package = not ("private" in parent_mods or "protected" in parent_mods)
                if "public" in modifiers or (def_type_full == "constructor" and is_parent_public_or_package and "private" not in modifiers and "protected" not in modifiers):
                     suggestion_text = (f"{change_verb} {visibility} {def_type_simple} `{method_name_for_note}({params_str})` (line {start_line}) in {filename}. Review/add JUnit tests for inputs, outputs, edge cases.")

            elif def_type_full == "field":
                field_type = definition_info.get('field_type', 'unknown_type'); description = f"{visibility} {def_type_simple} `{name}` of type `{field_type}` (declared line {start_line})"; findings['dependencies'].append(f"{change_verb} {description} in {filename}. Review usage.")
            if suggestion_text: findings['tests_suggestions'].append(suggestion_text)

    if ANALYSIS_JAVA_TEST_STUB_GEN in analyses_to_run:
        stubs_generated_count = 0
        original_module_path = filename; test_src_root_guess = ""; package_path_str = ""
        if "src/main/java/" in original_module_path: test_src_root_guess = original_module_path.replace("src/main/java/", "src/test/java/", 1); package_path_str = original_module_path.split("src/main/java/", 1)[-1]
        elif original_module_path.startswith("src/"): test_src_root_guess = original_module_path.replace("src/", "src/test/java/", 1); package_path_str = original_module_path.split("src/", 1)[-1]
        else: test_src_root_guess = os.path.join("src/test/java", os.path.basename(original_module_path)); package_path_str = os.path.basename(original_module_path)
        if package_path_str.endswith(".java"): package_path_str = os.path.dirname(package_path_str)
        package_name_from_path = package_path_str.replace(os.path.sep, '.') if package_path_str else None
        parsed_package_def = next((d for d in findings.get('java_definitions', []) if d['type'] == 'package'), None)
        current_package_name = parsed_package_def['name'] if parsed_package_def else (package_name_from_path if package_name_from_path else "")

        for definition_info in findings.get('java_definitions', []): # Iterate correlated definitions
            if definition_info.get('change_type') == 'new' and definition_info['type'] in ["ClassDeclaration", "InterfaceDeclaration", "EnumDeclaration"]:
                def_name = definition_info['name']; modifiers = definition_info.get('modifiers', []); def_type_simple = definition_info['type'].replace("Declaration","")
                if "private" in modifiers : continue
                class_to_import = f"{current_package_name}.{def_name}" if current_package_name else def_name
                test_class_name = f"{def_name}Test"

                # Construct suggested_test_filename relative to a base test source directory
                test_file_subpath = package_path_str.replace('.', os.path.sep) if package_name_from_path else ""
                # Ensure test_src_root_guess is a directory before joining
                base_test_dir = os.path.dirname(test_src_root_guess) if os.path.splitext(test_src_root_guess)[1] else test_src_root_guess
                suggested_test_filename = os.path.join(base_test_dir, test_file_subpath, test_class_name + ".java")

                methods_stubs_str = ""
                if definition_info['type'] == "ClassDeclaration":
                    # Add constructor stubs for classes
                    constructors = [m for m in definition_info.get('methods', []) if m['type'] == 'constructor' and m.get('change_type') == 'new' and ("public" in m.get('modifiers', []) or not any(vis in m.get('modifiers', []) for vis in ["private", "protected"]))]
                    if not constructors and "public" in definition_info.get('modifiers',[]): # Default constructor for public class
                         methods_stubs_str += f"""
    @Test
    void testDefaultConstructor_{def_name}() {{
        // TODO: Test default constructor for {def_name}
        // Example: {def_name} instance = new {def_name}();
        // assertNotNull(instance);
        throw new UnsupportedOperationException("Test for default constructor of {def_name} not implemented.");
    }}
"""
                    for member in constructors:
                        param_types_str = ', '.join(p[0] for p in member.get('parameters',[]))
                        test_method_name = f"testConstructor_{def_name}_{len(member.get('parameters',[]))}args" # Basic disambiguation
                        methods_stubs_str += f"""
    @Test
    void {test_method_name}() {{
        // TODO: Test constructor {def_name}({param_types_str})
        throw new UnsupportedOperationException("Test for constructor {def_name}({param_types_str}) not implemented.");
    }}
"""
                # Add stubs for new public methods
                for member in definition_info.get('methods', []):
                    member_name = member['name']; member_mods = member.get('modifiers', []); member_type = member['type']
                    if member_type == 'method' and "public" in member_mods and member.get('change_type') == 'new':
                        param_types_str = ', '.join(p[0] for p in member.get('parameters',[]))
                        test_method_name = f"test{member_name[0].upper() + member_name[1:]}" if len(member_name) > 0 else f"testMethod{stubs_generated_count}"
                        methods_stubs_str += f"""
    @Test
    void {test_method_name}() {{
        // TODO: Test method {member_name}({param_types_str}) of class {def_name}
        // Example: {def_name} instance = new {def_name}(); // or from @BeforeEach
        // {member.get('return_type', 'void')} result = instance.{member_name}(...);
        // assert...
        throw new UnsupportedOperationException("Test for method {member_name} in {def_name} not implemented.");
    }}
"""
                if not methods_stubs_str and definition_info['type'] == "InterfaceDeclaration" and "public" in definition_info.get('modifiers', []):
                    methods_stubs_str = f"\n    // TODO: Add tests for methods of interface {def_name} as they are implemented by concrete classes.\n"
                elif not methods_stubs_str and definition_info['type'] == "EnumDeclaration" and "public" in definition_info.get('modifiers', []):
                    methods_stubs_str = f"""
    @Test
    void testEnumValues() {{
        // TODO: Test enum {def_name} values and behaviors
        // Example: assertNotNull({def_name}.valueOf("SOME_VALUE"));
        throw new UnsupportedOperationException("Test for enum {def_name} not implemented.");
    }}
"""


                if methods_stubs_str or definition_info['type'] == "EnumDeclaration": # Generate class stub if there's something to test or it's an Enum
                    stub_code = f"""package {current_package_name};

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
// TODO: Adjust import if class under test is in a different package.
// import {class_to_import};

class {test_class_name} {{
    // TODO: Add setup, mock dependencies if needed (@BeforeEach)
{methods_stubs_str.strip()}
    // TODO: Add more test cases for other methods, edge cases, etc.
}}
"""
                    findings['java_test_stubs'].append({'target_definition_name': def_name, 'target_definition_type': def_type_simple, 'suggested_test_filename': suggested_test_filename.replace(os.path.sep, '/'), 'stub_code': stub_code.strip() }); stubs_generated_count+=1

        is_java_file_with_new_definitions = any(d.get('change_type')=='new' and d.get('type') in ["ClassDeclaration", "InterfaceDeclaration", "EnumDeclaration"] for d in findings.get('java_definitions',[]))
        if stubs_generated_count == 0:
            if ANALYSIS_JAVA_PARSER not in analyses_to_run: findings['impacts'].append(f"Java test stub generation skipped as Java parsing (source of definitions) was not run for {filename}.")
            elif not all_definitions_from_javalang : findings['impacts'].append(f"Java test stub generation: Java parser found no definitions in {filename} for stubbing.")
            elif not is_java_file_with_new_definitions: findings['impacts'].append(f"Java test stub generation: No new public classes/interfaces/enums found in {filename} for stubbing.")
            # Add a more general "no stubs generated" if it ran but found nothing to stub.
            elif is_java_file_with_new_definitions : findings['impacts'].append(f"Java test stub generation run for {filename}, but no suitable new public elements found for stubbing.")


    if file_content and ANALYSIS_JAVA_CHECKSTYLE in analyses_to_run:
        tmp_file_path = ""
        checkstyle_jar_cmd = os.getenv("CHECKSTYLE_JAR", "/tmp/checkstyle.jar")

        effective_checkstyle_config = DEFAULT_CHECKSTYLE_CONFIG
        if checkstyle_config_path:
            if os.path.exists(checkstyle_config_path):
                effective_checkstyle_config = checkstyle_config_path
                findings['impacts'].append(f"Using custom Checkstyle configuration: {checkstyle_config_path}")
            else:
                findings['impacts'].append(f"Custom Checkstyle config path '{checkstyle_config_path}' not found. Falling back to default: {DEFAULT_CHECKSTYLE_CONFIG}")

        if not os.path.exists(effective_checkstyle_config):
            findings['impacts'].append(f"Checkstyle config (effective: {effective_checkstyle_config}) not found. Skipping Checkstyle analysis for {filename}.")
        else:
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False, encoding='utf-8') as tmp_file:
                    tmp_file.write(file_content)
                    tmp_file_path = tmp_file.name

                cmd = ['java', '-jar', checkstyle_jar_cmd, '-c', effective_checkstyle_config, '-f', 'xml', tmp_file_path]
                process = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')
                stderr_output = process.stderr.strip()
                if stderr_output: print(f"Checkstyle stderr for {filename} (temp {tmp_file_path}): {stderr_output}");
                if "Exception" in stderr_output or "Error" in stderr_output or "Could not" in stderr_output: findings['impacts'].append(f"Checkstyle operational error for {filename} (see console logs).")
                if process.stdout: findings['linting_issues'] = _parse_checkstyle_xml_output(process.stdout, filename)
                elif not stderr_output: findings['linting_issues'] = []
            except FileNotFoundError: findings['impacts'].append(f"Checkstyle execution failed for {filename}. Ensure Java and '{checkstyle_jar_cmd}' are accessible.")
            except Exception as e: findings['impacts'].append(f"Error running Checkstyle on {filename}: {str(e)}")
            finally:
                if tmp_file_path and os.path.exists(tmp_file_path): os.remove(tmp_file_path)
    elif ANALYSIS_JAVA_CHECKSTYLE not in analyses_to_run: findings['impacts'].append(f"Checkstyle linting skipped for {filename}.")
    elif not file_content and ANALYSIS_JAVA_CHECKSTYLE in analyses_to_run: findings['impacts'].append(f"Checkstyle linting skipped for {filename} because full content was not available.")

    if patch_text and ANALYSIS_SECURITY_KEYWORD_SCAN in analyses_to_run:
        if not file_content and not any("full content not fetched" in imp for imp in findings['impacts']): findings['impacts'].append(f"Java file {filename} was modified (Status: {file_info.get('status', 'N/A')}, patch available but content fetch failed).")
        findings['security_issues'] = _perform_security_scan(patch_text) # Use the new helper
    elif not patch_text and not findings['impacts'] and not file_content : findings['impacts'].append(f"Java file {filename} (Status: {file_info.get('status', 'N/A')}) processed (no patch data, no content fetched).")

    if not findings['tests_suggestions']:
        if findings['linting_issues'] and ANALYSIS_JAVA_CHECKSTYLE in analyses_to_run: findings['tests_suggestions'].append(f"Review linting issues for {filename} and ensure test coverage.")
        elif file_content: findings['tests_suggestions'].append(f"Generic reminder: Ensure adequate JUnit test coverage for {filename}.")
        else: findings['tests_suggestions'].append(f"No content or patch data for {filename}. Review file status and ensure coverage.")
    return findings

def _analyze_maven_pom(file_info: Dict[str, Any], pr_data: Dict[str, Any], analyses_to_run: List[str]) -> Dict[str, Any]:
    # ... (Content from step 53 - correct)
    findings = {'file_path': file_info.get('filename'), 'language': 'maven_pom', 'build_dependency_changes': [], 'impacts': [], 'security_issues': [] } # Added security_issues for consistency
    filename = file_info.get('filename')
    if ANALYSIS_MAVEN_POM not in analyses_to_run:
        findings['impacts'].append(f"Maven pom.xml analysis skipped for {filename} as per configuration.")
        return findings
    owner = pr_data.get('owner'); repo = pr_data.get('repo'); head_sha = pr_data.get('head_sha'); file_content = None
    if owner and repo and head_sha and filename:
        api_headers = {"Accept": "application/vnd.github.v3+json"}; file_content = get_file_content_at_ref(owner, repo, filename, head_sha, api_headers)
    if not file_content: findings['impacts'].append(f"Content for {filename} not available. Skipping pom.xml analysis."); return findings
    try:
        root = ET.fromstring(file_content); namespace = ""
        if '}' in root.tag and root.tag.startswith('{'): namespace = root.tag.split('}')[0] + "}"
        all_declared_deps = []
        for dep_node in root.findall(f".//{namespace}dependency"):
            group_id = dep_node.findtext(f"{namespace}groupId", "N/A"); artifact_id = dep_node.findtext(f"{namespace}artifactId", "N/A"); version = dep_node.findtext(f"{namespace}version", "N/A")
            all_declared_deps.append(f"{group_id}:{artifact_id}:{version}")
        if not all_declared_deps: findings['impacts'].append(f"No <dependency> tags found in {filename} with current parsing logic.")
        patch_text = file_info.get('patch')
        if patch_text:
            added_dep_lines = 0; version_change_hints = 0
            for line in patch_text.splitlines():
                if line.startswith('+') and "<dependency>" in line: added_dep_lines +=1
                if line.startswith('+') and "<version>" in line and "</version>" in line: version_change_hints +=1
            if file_info.get('status') == 'added': findings['build_dependency_changes'].append(f"New pom.xml added. Declared dependencies ({len(all_declared_deps)}): {', '.join(all_declared_deps[:3])}" + (f", ... and {len(all_declared_deps)-3} more" if len(all_declared_deps) > 3 else "") + ". Review all declared dependencies.")
            elif added_dep_lines > 0: findings['build_dependency_changes'].append(f"Potentially {added_dep_lines} new/modified <dependency> block(s) added/changed in {filename}. Review PR diff. Current full list has {len(all_declared_deps)} dependencies.")
            elif version_change_hints > 0: findings['build_dependency_changes'].append(f"Detected {version_change_hints} direct <version> tag additions/changes in {filename}. Review PR diff for specific version updates.")
            elif all_declared_deps : findings['build_dependency_changes'].append(f"pom.xml was modified. No new <dependency> tags directly detected in patch lines, but review changes carefully. Total declared dependencies: {len(all_declared_deps)}.")
        elif all_declared_deps: findings['impacts'].append(f"Parsed {filename}. Found {len(all_declared_deps)} dependencies.")
    except ET.ParseError as e: findings['impacts'].append(f"Could not parse {filename} as XML: {e}")
    except Exception as e: findings['impacts'].append(f"Unexpected error during {filename} analysis: {str(e)}")
    return findings

def _analyze_other_file(file_info: Dict[str, Any], pr_data: Dict[str, Any], analyses_to_run: List[str]) -> Dict[str, Any]:
    patch_text = file_info.get('patch')
    security_issues_other = []
    if patch_text and ANALYSIS_SECURITY_KEYWORD_SCAN in analyses_to_run:
        security_issues_other = _perform_security_scan(patch_text)
    return {'file_path': file_info.get('filename'), 'language': 'other', 'impacts': [f"Non-code file changed: {file_info.get('filename')} (Status: {file_info.get('status', 'N/A')})"], 'dependencies': [], 'tests_suggestions': [], 'security_issues': security_issues_other, 'linting_issues': [], 'raw_analysis_data': {}}

def _perform_security_scan(patch_text: str) -> List[str]:
    """
    Scans patch text for configured keywords and regex patterns.
    """
    detected_issues = []
    if not patch_text:
        return detected_issues

    # Check for keywords
    for keyword in SECURITY_SCAN_CONFIG.get("keywords", []):
        if keyword in patch_text:
            detected_issues.append(f"Potential security keyword '{keyword}' found in changed lines.")

    # Check for regex patterns
    for pattern_info in SECURITY_SCAN_CONFIG.get("patterns", []):
        pattern = pattern_info.get("pattern") # This is already a compiled regex object
        pattern_name = pattern_info.get("name", "Unnamed Pattern")
        if pattern and pattern.search(patch_text): # Ensure pattern is not None (if compilation failed)
            detected_issues.append(f"Potential security pattern '{pattern_name}' matched in changed lines.")

    return detected_issues

def analyze_code_changes(
    pr_data: Dict[str, Any],
    analyses_to_run: List[str],
    checkstyle_config_path: Optional[str] = None,
    flake8_options_str: Optional[str] = None
) -> Dict[str, Any]:
    if not pr_data or 'files_changed' not in pr_data:
        print("Error: Invalid PR data provided for analysis in analyze_code_changes.")
        return {'overall_summary': {'reuse_suggestions': [], 'solid_violations': [], 'general_security_reminders': []}, 'file_specific_findings': []}

    # Ensure security config is loaded (it's called at module load, but good for robustness if module structure changes)
    if not SECURITY_SCAN_CONFIG["keywords"] and not SECURITY_SCAN_CONFIG["patterns"] and os.path.exists(SECURITY_SCAN_CONFIG_PATH) :
        print("Re-attempting to load security scan config as it seems empty...")
        _load_security_scan_config()


    print(f"Analyzing PR (multi-language): {pr_data.get('title', 'N/A')} with active analyses: {analyses_to_run}"); file_specific_findings_list = []
    for file_info in pr_data.get('files_changed', []):
        filename = file_info.get('filename', '');
        if not filename: continue
        if filename.endswith('.py'):
            findings = _analyze_python_file(file_info, pr_data, analyses_to_run, flake8_options_str=flake8_options_str)
        elif filename.endswith('.java'):
            findings = _analyze_java_file(file_info, pr_data, analyses_to_run, checkstyle_config_path=checkstyle_config_path)
        elif os.path.basename(filename) == 'pom.xml':
            findings = _analyze_maven_pom(file_info, pr_data, analyses_to_run)
        else:
            findings = _analyze_other_file(file_info, pr_data, analyses_to_run)
        file_specific_findings_list.append(findings)
    overall_reuse_suggestions = []; overall_solid_violations = []; general_security_reminders = []
    if len(pr_data.get('files_changed', [])) > 1: overall_reuse_suggestions.append("Consider if there are common patterns across the changed files that could be abstracted globally.")
    overall_solid_violations.append("Reminder: Review all code changes for adherence to SOLID principles.")
    if ANALYSIS_SECURITY_KEYWORD_SCAN in analyses_to_run and \
       any(f_item.get('security_issues') for f_item in file_specific_findings_list): # Check if any file had security issues
         general_security_reminders.append("Overall Security Reminder: Potential security items identified. Please review all reported security concerns carefully.")
    elif ANALYSIS_SECURITY_KEYWORD_SCAN in analyses_to_run:
         general_security_reminders.append("Overall Security Reminder: Security scan was active. Ensure manual review for any subtle security implications not caught by automated checks.")

    return {'overall_summary': {'reuse_suggestions': overall_reuse_suggestions, 'solid_violations': overall_solid_violations, 'general_security_reminders': general_security_reminders}, 'file_specific_findings': file_specific_findings_list}
