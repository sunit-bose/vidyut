# src/code_analyzer.py

import ast
import re # For parsing line numbers from patch
import javalang # Added for Java analysis

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
    # Consider adding more, but be mindful of false positives.
    # Example: "eval(", "exec(", "dangerouslySetInnerHTML" (for JS/React if ever supported)
]

# Placeholder for future Python AST analysis
def _analyze_python_file(file_info, pr_data):
    """Analyzes a single Python file."""
    findings = {
        'file_path': file_info.get('filename'),
        'language': 'python',
        'impacts': [], # Specific impacts related to this file
        'dependencies': [], # e.g., changed functions/classes used by others
        'tests_suggestions': [], # Specific test ideas
        'security_issues': [], # Python-specific security findings
        'raw_analysis_data': {} # For more complex data if needed later
    }

    filename = file_info.get('filename')
    patch_text = file_info.get('patch')
    findings['impacts'] = [] # Reset default impact

    if not patch_text:
        findings['impacts'].append(f"Python file {filename} changed, but no patch data available for AST analysis in this pass.")
        # Keep the generic test suggestion if no patch is available
        findings['tests_suggestions'].append(f"Consider adding/updating unit tests for changes in {filename}.")
        return findings

    # Helper to get line numbers from hunk headers (e.g., "@@ -15,7 +15,9 @@")
    def get_changed_line_ranges(patch_text):
        ranges = []
        for line in patch_text.splitlines():
            if line.startswith("@@"):
                match = re.search(r"\+([0-9]+)(?:,([0-9]+))?", line)
                if match:
                    start_line = int(match.group(1))
                    length = int(match.group(2) or 1) # if length is not there, it's 1 line
                    if length == 0: # In some diffs, ,0 means no lines on this side (e.g. empty file added then content added)
                                    # or when a file is deleted, the + side might be x,0
                        # For our purpose, we care about lines on the '+' side that exist.
                        # A length of 0 on the '+' side in a hunk usually means nothing was added there,
                        # or it's the context before a deletion.
                        # We are interested in lines that *are* in the new version.
                        # If length is 0, it implies no lines from the "new" file in that part of the hunk.
                        # We can skip these or handle them if we want to mark deletion points.
                        # For now, we'll focus on hunks that add/modify lines.
                        if length > 0 : # Only consider if new lines are present
                           ranges.append((start_line, length))
                    else:
                        ranges.append((start_line, length))
        return ranges

    changed_line_info = get_changed_line_ranges(patch_text) # List of (start_line, num_lines) for additions/modifications

    # --- Attempt to get full file content (Simulated for now) ---
    # This is where we would ideally fetch the full content of the file from the PR's head.
    # For now, we'll simulate having it or acknowledge this limitation.
    # If we had the full file content as `file_content_str`:
    # try:
    #     tree = ast.parse(file_content_str)
    # except SyntaxError as e:
    #     findings['impacts'].append(f"Could not parse Python file {filename} due to SyntaxError: {e}")
    #     return findings
    # ---- End Simulation ----

    # For this subtask, we cannot parse the full file yet as it's not fetched.
    # We will simulate finding function/class defs and checking if their
    # line numbers (if we had them from a full AST) overlap with `changed_line_info`.
    # This is a placeholder for true AST analysis of the full file.

    findings['impacts'].append(f"Python file {filename} was modified. (Status: {file_info.get('status', 'N/A')})") # General impact
    findings['tests_suggestions'] = [] # Clear placeholder from initial setup

    # Simulate finding function/class definitions and checking against patch lines
    # This is highly simplified due to not having the full AST of the actual file.
    # A real implementation would parse the full file, then iterate `ast.walk(tree)`.

    # Example of how one might check if a definition is affected by changes:
    # Assume we found a function `def example_func():` at line 50, ending line 55 (from full file AST)
    # func_start_line, func_end_line = 50, 55
    # for change_start, change_length in changed_line_info:
    #   change_end = change_start + change_length -1 # 0-length changes won't make sense here
    #   if change_length > 0 and max(func_start_line, change_start) <= min(func_end_line, change_end):
    #       findings['tests_suggestions'].append(f"Function/Class 'example_func' (lines {func_start_line}-{func_end_line}) seems affected by changes. Review and test.")
    #       break

    # Since we can't do the above properly yet, add a more generic suggestion based on patch presence
    if changed_line_info:
        findings['tests_suggestions'].append(f"Changes detected in {filename} (affected code hunks: {len(changed_line_info)}). Consider specific unit tests for modified logic.")
        findings['dependencies'].append(f"Review changes in {filename} for potential impacts on dependent modules or functions (manual check for now).")
    else: # No changed lines info from patch, or patch was empty
        findings['tests_suggestions'].append(f"Patch data for {filename} did not yield specific line change information for targeted testing suggestions. Review changes broadly.")


    # Placeholder for actual signature change detection
    # findings['dependencies'].append("If function signatures changed, update call sites.")

    # Placeholder for AST-based security checks (very basic example)
    # A real check would parse code and look for specific AST patterns.
    # For example, looking for `call` nodes where `id` is `eval`.
    # if "eval(" in patch_text: # Super naive check, prone to false positives/negatives
    #    findings['security_issues'].append(f"Potential use of 'eval' detected in changes in {filename}. Review carefully for security implications.")

    # Rudimentary security keyword scan
    if patch_text:
        for keyword in RUDIMENTARY_SECURITY_KEYWORDS:
            if keyword in patch_text: # Simple substring check
                findings['security_issues'].append(
                    f"Potential security keyword '{keyword}' found in changes."
                )
        # Optional: Add a note if no keywords found - usually only report if an issue is found.
        # if not findings['security_issues']:
        #     findings['security_issues'].append("No obvious rudimentary security keywords found in patch.")

    if not findings['tests_suggestions']: # Fallback if no other specific test suggestions were added
         findings['tests_suggestions'].append(f"Generic reminder: Ensure adequate test coverage for {filename}.")

    return findings # Return the findings dictionary

# Placeholder for future Java analysis
def _analyze_java_file(file_info, pr_data):
    """Analyzes a single Java file."""
    findings = {
        'file_path': file_info.get('filename'),
        'language': 'java',
        'impacts': [],
        'dependencies': [],
        'tests_suggestions': [],
        'security_issues': [],
        'raw_analysis_data': {}
    }
    filename = file_info.get('filename')
    patch_text = file_info.get('patch') # May be None
    findings['impacts'] = [] # Reset default impact
    findings['tests_suggestions'] = [] # Clear placeholder

    # --- Full file content needed for javalang parsing ---
    # This is where we would ideally have the full content of the Java file.
    # For now, we acknowledge this limitation.
    # Example: file_content_str = fetch_full_java_file_content(filename, pr_data)
    #
    # if file_content_str:
    #     try:
    #         tree = javalang.parse.parse(file_content_str)
    #         findings['impacts'].append(f"Successfully parsed Java file {filename} (basic structure).")
    #
    #         for path, node in tree:
    #             if isinstance(node, javalang.tree.ClassDeclaration):
    #                 findings['impacts'].append(f"Found class declaration: {node.name}")
    #                 # Check if this class's line numbers overlap with patch changes
    #             elif isinstance(node, javalang.tree.MethodDeclaration):
    #                 findings['tests_suggestions'].append(f"Method found: {node.name}. Consider JUnit tests if new or modified.")
    #
    #     except javalang.parser.JavaSyntaxError as e:
    #         findings['impacts'].append(f"Could not parse Java file {filename} due to SyntaxError: {e.message}")
    #     except Exception as e:
    #         findings['impacts'].append(f"Error during basic javalang parsing of {filename}: {str(e)}")
    # else:
    #     findings['impacts'].append(f"Java file {filename} changed, but full content not available for javalang analysis in this pass.")
    # ---- End Simulation of javalang parsing ----

    # For this subtask, as full content fetching is not yet implemented,
    # provide generic feedback based on patch presence.
    if patch_text:
        findings['impacts'].append(f"Java file {filename} was modified (changes detected in patch). (Status: {file_info.get('status', 'N/A')})")
        findings['tests_suggestions'].append(f"Review changes in {filename} and consider specific JUnit tests for modified logic.")
        findings['dependencies'].append(f"Manual check: Review changes in {filename} for impacts on dependent Java classes or interfaces.")
    else:
        findings['impacts'].append(f"Java file {filename} changed, but no patch data available for detailed review in this pass. (Status: {file_info.get('status', 'N/A')})")
        findings['tests_suggestions'].append(f"Generic reminder: Ensure adequate JUnit test coverage for {filename}.")

    # Rudimentary security keyword scan
    if patch_text:
        for keyword in RUDIMENTARY_SECURITY_KEYWORDS:
            if keyword in patch_text: # Simple substring check
                findings['security_issues'].append(
                    f"Potential security keyword '{keyword}' found in changes."
                )
        # Optional: Add a note if no keywords found
        # if not findings['security_issues']:
        #     findings['security_issues'].append("No obvious rudimentary security keywords found in patch.")

    return findings # Return the findings dictionary

# Placeholder for other file types
def _analyze_other_file(file_info, pr_data):
    """Analyzes other file types (e.g., markdown, text)."""
    findings = {
        'file_path': file_info.get('filename'),
        'language': 'other',
        'impacts': [f"Non-code file changed: {file_info['filename']} (Status: {file_info.get('status', 'N/A')})"],
        'dependencies': [],
        'tests_suggestions': [],
        'security_issues': [],
        'raw_analysis_data': {}
    }
    return findings


def analyze_code_changes(pr_data):
    """
    Analyzes the code changes in a PR to identify impact areas,
    suggest code reuse, and lint for SOLID design patterns.
    This version dispatches to language-specific analyzers.

    Args:
        pr_data (dict): A dictionary containing PR details,
                        especially 'files_changed'.

    Returns:
        dict: An aggregated dictionary of analysis results.
              Example: {
                  'overall_summary': {
                      'reuse_suggestions': [],
                      'solid_violations': [],
                      'general_security_reminders': []
                  },
                  'file_specific_findings': [
                      # list of findings dicts from _analyze_python_file, _analyze_java_file etc.
                  ]
              }
    """
    if not pr_data or 'files_changed' not in pr_data:
        print("Error: Invalid PR data provided for analysis in analyze_code_changes.")
        return {
            'overall_summary': {
                'reuse_suggestions': [],
                'solid_violations': [],
                'general_security_reminders': []
            },
            'file_specific_findings': []
        }

    print(f"Analyzing PR (multi-language): {pr_data.get('title', 'N/A')}")

    file_specific_findings_list = []

    for file_info in pr_data.get('files_changed', []):
        filename = file_info.get('filename', '')
        # We need the actual file content for AST parsing, not just the patch.
        # The 'patch' from GitHub API file details is useful, but for full AST,
        # we'd typically fetch the file content at the PR's head commit.
        # This will be a consideration for the next steps when implementing AST.
        # For now, dispatch based on filename. 'patch' key check remains for impact areas.

        if not filename: # Should not happen if GitHub API data is valid
            continue

        if filename.endswith('.py'):
            findings = _analyze_python_file(file_info, pr_data)
            file_specific_findings_list.append(findings)
        elif filename.endswith('.java'):
            findings = _analyze_java_file(file_info, pr_data)
            file_specific_findings_list.append(findings)
        else:
            # For .md, .txt, or other non-code files, or files not yet supported
            findings = _analyze_other_file(file_info, pr_data)
            file_specific_findings_list.append(findings)

    # Placeholder for overall analysis (reuse, SOLID) - can be enhanced later
    overall_reuse_suggestions = []
    if len(pr_data.get('files_changed', [])) > 1:
        overall_reuse_suggestions.append("Consider if there are common patterns across the changed files that could be abstracted globally.")

    overall_solid_violations = ["Reminder: Review all code changes for adherence to SOLID principles."]

    # This general security reminder might be superseded or enhanced by file-specific ones later
    general_security_reminders = []
    # Check if any of the processed files are Python or Java to add a general reminder
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
    # Example Usage (with mock data for now)
    mock_pr_data_py = {
        'title': 'Test PR - Python Changes',
        'files_changed': [
            {'filename': 'src/module_a/file1.py', 'status': 'modified', 'patch': '...'},
            {'filename': 'docs/README.md', 'status': 'modified', 'patch': '...'}
        ]
    }
    analysis_results_py = analyze_code_changes(mock_pr_data_py)
    print("\nPython PR Analysis Results:")
    print(f"Overall: {analysis_results_py['overall_summary']}")
    for finding in analysis_results_py['file_specific_findings']:
        print(f"File ({finding['language']}): {finding['file_path']} - Impacts: {finding['impacts']}")

    mock_pr_data_java = {
        'title': 'Test PR - Java Changes',
        'files_changed': [
            {'filename': 'com/example/Main.java', 'status': 'added', 'patch': '...'},
            {'filename': 'com/example/Util.java', 'status': 'modified', 'patch': '...'},
        ]
    }
    analysis_results_java = analyze_code_changes(mock_pr_data_java)
    print("\nJava PR Analysis Results:")
    print(f"Overall: {analysis_results_java['overall_summary']}")
    for finding in analysis_results_java['file_specific_findings']:
        print(f"File ({finding['language']}): {finding['file_path']} - Impacts: {finding['impacts']}")
