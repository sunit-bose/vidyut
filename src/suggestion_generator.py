# src/suggestion_generator.py

def generate_suggestions(analysis_results):
    """
    Generates actionable suggestions based on multi-language code analysis results.

    Args:
        analysis_results (dict): A dictionary from the code_analyzer,
                                 with 'overall_summary' and 'file_specific_findings'.
    Returns:
        list: A list of strings, where each string is a suggestion.
    """
    if analysis_results is None: # Check for None specifically
        print("Error: No analysis results provided for suggestion generation.")
        return []

    suggestions = []

    # Overall suggestions from summary
    overall_summary = analysis_results.get('overall_summary', {})
    for reuse_idea in overall_summary.get('reuse_suggestions', []):
        suggestions.append(f"Overall Code Reuse: {reuse_idea}")
    for violation in overall_summary.get('solid_violations', []):
        suggestions.append(f"Overall Design Pattern: {violation}")
    for reminder in overall_summary.get('general_security_reminders', []):
        suggestions.append(reminder) # Already a full sentence

    # File-specific suggestions
    file_findings = analysis_results.get('file_specific_findings', [])

    if not file_findings and not suggestions:
        return ["No specific suggestions based on the current analysis. General best practices still apply."]

    for finding in file_findings:
        file_path = finding.get('file_path', 'N/A')
        language = finding.get('language', 'unknown')

        suggestions.append(f"--- File: {file_path} ({language}) ---")

        impacts = finding.get('impacts', [])
        for impact in impacts:
            suggestions.append(f"  Impact: {impact}")

        if language in ['python', 'java']:
            dependencies = finding.get('dependencies', [])
            for dep_note in dependencies:
                suggestions.append(f"  Dependency Note: {dep_note}")

            tests_suggestions = finding.get('tests_suggestions', [])
            for test_sugg in tests_suggestions:
                suggestions.append(f"  Testing Suggestion: {test_sugg}")

            security_issues = finding.get('security_issues', [])
            for sec_issue in security_issues:
                suggestions.append(f"  Security Concern: {sec_issue}")

            linting_issues = finding.get('linting_issues', [])
            if linting_issues:
                linter_name = "Flake8" if language == "python" else "Checkstyle" if language == "java" else "Linter"
                suggestions.append(f"  Linting Issues ({language} - {linter_name}):")
                for issue in linting_issues:
                    severity_info = f" (Severity: {issue.get('severity', 'info')})" if language == "java" else ""
                    suggestions.append(
                        f"    L{issue['line']}:{issue.get('column',0)} [{issue.get('code','N/A')}] {issue.get('message', 'N/A')}{severity_info}"
                    )

            if language == 'python':
                python_test_stubs = finding.get('python_test_stubs', [])
                if python_test_stubs:
                    suggestions.append(f"  Generated Python Test Stubs:")
                    for stub_info in python_test_stubs:
                        target_name = stub_info.get('target_definition_name', 'N/A')
                        target_type = stub_info.get('target_definition_type', 'definition')
                        suggested_file = stub_info.get('suggested_test_filename', 'N/A')
                        stub_code = stub_info.get('stub_code', '# No stub code generated.')

                        suggestions.append(
                            f"    - For new {target_type} `{target_name}` (in {file_path}):"
                        )
                        suggestions.append(
                            f"      Suggested Test File: `{suggested_file}`"
                        )
                        suggestions.append(
                            f"      Boilerplate Code:\n```python\n{stub_code}\n```"
                        )
                    suggestions.append("    (Note: These are basic stubs. Please review, adjust paths, and implement test logic.)")

            if not any([dependencies, tests_suggestions, security_issues, linting_issues,
                        (python_test_stubs if language == 'python' else [])]):
                 suggestions.append(f"  No further specific code analysis suggestions for this {language} file in this phase.")

        elif language == 'other':
            if not impacts:
                suggestions.append(f"  No specific findings for this file.")

    if not suggestions:
        suggestions.append("No actionable suggestions were generated from the analysis. Please review the code manually.")

    return suggestions

if __name__ == '__main__':
    mock_analysis = {
        'overall_summary': {
            'reuse_suggestions': ['Consider shared libraries.'],
            'solid_violations': ['Review SOLID adherence.'],
            'general_security_reminders': ['Check for common vulnerabilities.']
        },
        'file_specific_findings': [
            {
                'file_path': 'src/main.py',
                'language': 'python',
                'impacts': ['Python file src/main.py was modified significantly.'],
                'dependencies': ['Dependency: `old_function` might be affected by changes to `new_function`.'],
                'tests_suggestions': ['Testing: Add unit tests for new Python functions in src/main.py'],
                'security_issues': ["Potential security keyword 'HARDCODED_API_KEY' found."],
                'linting_issues': [
                    {'file': 'src/main.py', 'line': 10, 'column': 1, 'code': 'E302', 'message': 'expected 2 blank lines, found 1'}
                ],
                'python_test_stubs': [
                    {
                        'target_definition_name': 'my_new_utility_func',
                        'target_definition_type': 'function',
                        'suggested_test_filename': 'tests/test_main.py',
                        'stub_code': 'import unittest\n# TODO: from src.main import my_new_utility_func\n\nclass TestMyNewUtilityFunc(unittest.TestCase):\n    def test_basic(self):\n        # TODO: Implement test\n        self.fail("Test not implemented")\n\nif __name__ == "__main__":\n    unittest.main()'
                    }
                ]
            },
            {
                'file_path': 'com/App.java',
                'language': 'java',
                'impacts': ['Java file com/App.java was added.'],
                'dependencies': [],
                'tests_suggestions': ['Testing: Ensure JUnit tests cover `App.java`.'],
                'security_issues': [],
                'linting_issues': [
                    {'file': 'com/App.java', 'line': 5, 'column': 10, 'code': 'TypeNameCheck', 'message': 'Name TooShort must match pattern.', 'severity': 'error'}
                ]
            },
            {
                'file_path': 'README.md', 'language': 'other',
                'impacts': ['Documentation file README.md was updated.']
            }
        ]
    }

    generated_suggestions = generate_suggestions(mock_analysis)
    print("\nGenerated Suggestions (Multi-Language with Stubs):")
    for sugg in generated_suggestions:
        print(sugg)

    empty_analysis = {
        'overall_summary': {},
        'file_specific_findings': []
    }
    generated_suggestions_empty = generate_suggestions(empty_analysis)
    print("\nGenerated Suggestions (Empty Analysis):")
    for sugg in generated_suggestions_empty:
        print(sugg)
