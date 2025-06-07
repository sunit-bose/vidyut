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

    # If there are no file_findings AND no overall suggestions have been added yet,
    # then it's appropriate to return the "No specific suggestions" message.
    if not file_findings and not suggestions:
        return ["No specific suggestions based on the current analysis. General best practices still apply."]

    # has_any_file_specific_actionable_item = False # Can be removed or adapted if needed later
    for finding in file_findings:
        file_path = finding.get('file_path', 'N/A')
        language = finding.get('language', 'unknown')

        suggestions.append(f"--- File: {file_path} ({language}) ---")

        # Always show impacts if present
        impacts = finding.get('impacts', [])
        for impact in impacts:
            suggestions.append(f"  Impact: {impact}")

        if language in ['python', 'java']: # Only show these for code files
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
                    # For Checkstyle, severity might be available and useful
                    severity_info = f" (Severity: {issue.get('severity', 'info')})" if language == "java" else ""
                    suggestions.append(
                        f"    L{issue['line']}:{issue.get('column',0)} [{issue.get('code','N/A')}] {issue.get('message', 'N/A')}{severity_info}"
                    )

            # If it's a code file but no specific suggestions were generated from the above categories
            # The 'impacts' are always shown if present (handled above).
            # This checks if there were no other specific findings for code files.
            if not any([dependencies, tests_suggestions, security_issues, linting_issues]): # Added linting_issues here
                 suggestions.append(f"  No further specific code analysis suggestions for this {language} file in this phase.")

        elif language == 'other':
            # For 'other' files, impacts are usually the only relevant info from current analysis.
            # If impacts were shown, we might not need to say more.
            # If there were no impacts (e.g., empty patch or error in analysis for 'other'),
            # then this note might be useful.
            if not impacts:
                suggestions.append(f"  No specific findings for this file.")
            # Optionally, explicitly state that detailed code analysis is not applicable:
            # else:
            #    suggestions.append(f"  (File type '{language}' - detailed code analysis not applicable or not yet implemented)")


    # If after processing everything, the only suggestions are from overall_summary
    # and there were no actionable file-specific items (e.g. only "No specific code analysis suggestions..."),
    # it might still look like "no specific suggestions".
    # However, the current logic will list file headers even if they have no sub-points.
    # This is okay for now. The final check is more of a fallback.
    if not suggestions:
        suggestions.append("No actionable suggestions were generated from the analysis. Please review the code manually.")

    return suggestions

if __name__ == '__main__':
    # Example Usage (with mock multi-language analysis data)
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
                'impacts': ['Python file src/main.py was modified.'],
                'tests_suggestions': ['Add tests for new Python functions in src/main.py']
            },
            {
                'file_path': 'com/App.java',
                'language': 'java',
                'impacts': ['Java file com/App.java was added.'],
                'tests_suggestions': ['Add JUnit tests for com/App.java']
            },
            {
                'file_path': 'README.md',
                'language': 'other',
                'impacts': ['Non-code file README.md was modified.']
                # No other specific suggestions for 'other' type in this mock
            }
        ]
    }

    generated_suggestions = generate_suggestions(mock_analysis)
    print("\nGenerated Suggestions (Multi-Language):")
    for sugg in generated_suggestions:
        print(sugg)

    empty_analysis = {
        'overall_summary': {
            'reuse_suggestions': [], 'solid_violations': [], 'general_security_reminders': []
        },
        'file_specific_findings': []
    }
    generated_suggestions_empty = generate_suggestions(empty_analysis)
    print("\nGenerated Suggestions (Empty Analysis - structure present but no findings):")
    for sugg in generated_suggestions_empty:
        print(sugg)

    none_analysis = None
    generated_suggestions_none = generate_suggestions(none_analysis)
    print("\nGenerated Suggestions (None Analysis):")
    # This will print the error message from within the function and return []
    # So, the loop won't run.
    if not generated_suggestions_none:
        print("(No suggestions returned, error message printed by function)")

    # Example: File listed but no specific sub-findings from analyzer
    mock_analysis_file_no_sub_findings = {
        'overall_summary': {},
        'file_specific_findings': [
            { 'file_path': 'config.yaml', 'language': 'other', 'impacts': ["Config changed."]}
        ]
    }
    generated_suggestions_no_sub = generate_suggestions(mock_analysis_file_no_sub_findings)
    print("\nGenerated Suggestions (File with impact but no other specific points):")
    for sugg in generated_suggestions_no_sub:
        print(sugg)
