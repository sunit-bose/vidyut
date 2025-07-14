# src/suggestion_generator.py
from src.code_analyzer import (
    ANALYSIS_PYTHON_AST, ANALYSIS_FLAKE8, ANALYSIS_JAVA_CHECKSTYLE,
    ANALYSIS_SECURITY_KEYWORD_SCAN, ANALYSIS_PYTHON_TEST_STUB_GEN,
    ANALYSIS_JAVA_PARSER, ANALYSIS_MAVEN_POM, ANALYSIS_JAVA_TEST_STUB_GEN
)

def generate_suggestions(analysis_results: dict) -> list[dict]:
    """
    Generates actionable suggestions as structured data based on code analysis results.

    Args:
        analysis_results (dict): A dictionary from the code_analyzer,
                                 with 'overall_summary' and 'file_specific_findings'.
    Returns:
        list[dict]: A list of dictionaries, where each dictionary is a structured suggestion.
    """
    if analysis_results is None:
        print("Error: No analysis results provided for suggestion generation.")
        return [{"type": "error", "message": "No analysis results provided."}]

    structured_suggestions = []

    overall_summary = analysis_results.get('overall_summary', {})
    for reuse_idea in overall_summary.get('reuse_suggestions', []):
        structured_suggestions.append({"type": "general_summary", "category": "code_reuse", "message": reuse_idea})
    for violation in overall_summary.get('solid_violations', []):
        structured_suggestions.append({"type": "general_summary", "category": "design_pattern", "message": violation})
    for reminder in overall_summary.get('general_security_reminders', []):
        structured_suggestions.append({"type": "general_summary", "category": "security_reminder", "message": reminder})

    file_findings = analysis_results.get('file_specific_findings', [])

    if not file_findings and not structured_suggestions:
        structured_suggestions.append({"type": "info", "message": "No specific suggestions based on the current analysis. General best practices still apply."})
        return structured_suggestions

    for finding in file_findings:
        file_path = finding.get('file_path', 'N/A')
        language = finding.get('language', 'unknown')

        structured_suggestions.append({
            "type": "file_marker",
            "file_path": file_path,
            "language": language
        })

        impacts = finding.get('impacts', [])
        for impact_text in impacts:
            structured_suggestions.append({
                "type": "file_impact",
                "file_path": file_path,
                "message": impact_text
            })

        if language == 'python':
            dependencies = finding.get('dependencies', [])
            for dep_note in dependencies:
                structured_suggestions.append({
                    "type": "dependency_note",
                    "file_path": file_path,
                    "language": "python",
                    "message": dep_note
                })

            tests_suggestions_list = finding.get('tests_suggestions', [])
            for test_sugg in tests_suggestions_list:
                structured_suggestions.append({
                    "type": "test_suggestion",
                    "file_path": file_path,
                    "language": "python",
                    "message": test_sugg
                })

            security_issues = finding.get('security_issues', []) # From keyword scan
            for sec_issue in security_issues:
                structured_suggestions.append({
                    "type": "security_concern",
                    "file_path": file_path,
                    "language": "python",
                    "message": sec_issue, # Contains "keyword 'X' found"
                    "severity": "warning"
                })

            linting_issues = finding.get('linting_issues', [])
            if linting_issues:
                for issue in linting_issues:
                    structured_suggestions.append({
                        "type": "linting",
                        "linter": "flake8",
                        "file_path": file_path,
                        "line_number": issue.get('line'),
                        "column_number": issue.get('column'),
                        "code": issue.get('code'),
                        "message": issue.get('message'),
                        "severity": "info" # Flake8 doesn't specify severity, default to info
                    })

            python_test_stubs = finding.get('python_test_stubs', [])
            if python_test_stubs:
                for stub_info in python_test_stubs:
                    structured_suggestions.append({
                        "type": "python_test_stub",
                        "file_path": file_path, # Source file path
                        "target_definition_name": stub_info.get('target_definition_name'),
                        "target_definition_type": stub_info.get('target_definition_type'),
                        "suggested_test_filename": stub_info.get('suggested_test_filename'),
                        "details": stub_info.get('stub_code') # The code itself
                    })
                structured_suggestions.append({
                    "type": "info",
                    "file_path": file_path,
                    "message": "Python test stubs are basic. Review, adjust paths, and implement test logic."
                })

            if not any([dependencies, tests_suggestions_list, security_issues, linting_issues, python_test_stubs, impacts]): # Check impacts too
                 structured_suggestions.append({
                     "type": "info",
                     "file_path": file_path,
                     "language": "python",
                     "message": f"No specific code analysis suggestions for this Python file in this phase."
                 })

        elif language == 'java':
            dependencies = finding.get('dependencies', [])
            for dep_note in dependencies:
                structured_suggestions.append({
                    "type": "dependency_note",
                    "file_path": file_path,
                    "language": "java",
                    "message": dep_note
                })

            tests_suggestions_list = finding.get('tests_suggestions', [])
            for test_sugg in tests_suggestions_list:
                structured_suggestions.append({
                    "type": "test_suggestion",
                    "file_path": file_path,
                    "language": "java",
                    "message": test_sugg
                })

            security_issues = finding.get('security_issues', []) # From keyword scan
            for sec_issue in security_issues:
                structured_suggestions.append({
                    "type": "security_concern",
                    "file_path": file_path,
                    "language": "java",
                    "message": sec_issue,
                    "severity": "warning"
                })

            linting_issues = finding.get('linting_issues', [])
            if linting_issues:
                for issue in linting_issues:
                    structured_suggestions.append({
                        "type": "linting",
                        "linter": "checkstyle",
                        "file_path": file_path,
                        "line_number": issue.get('line'),
                        "column_number": issue.get('column'),
                        "code": issue.get('code'), # Checkstyle rule name
                        "message": issue.get('message'),
                        "severity": issue.get('severity', 'info')
                    })

            java_test_stubs = finding.get('java_test_stubs', [])
            if java_test_stubs:
                for stub_info in java_test_stubs:
                    structured_suggestions.append({
                        "type": "java_test_stub",
                        "file_path": file_path, # Source file path
                        "target_definition_name": stub_info.get('target_definition_name'),
                        "target_definition_type": stub_info.get('target_definition_type'),
                        "suggested_test_filename": stub_info.get('suggested_test_filename'),
                        "details": stub_info.get('stub_code')
                    })
                structured_suggestions.append({
                    "type": "info",
                    "file_path": file_path,
                    "message": "Java test stubs (JUnit 5) are basic. Review, adjust imports/paths, and implement test logic."
                })

            if not any([dependencies, tests_suggestions_list, security_issues, linting_issues, java_test_stubs, impacts]):
                 structured_suggestions.append({
                     "type": "info",
                     "file_path": file_path,
                     "language": "java",
                     "message": f"No specific code analysis suggestions for this Java file in this phase."
                 })

        elif language == 'maven_pom':
            build_dep_changes = finding.get('build_dependency_changes', [])
            if build_dep_changes:
                for change_note in build_dep_changes:
                    structured_suggestions.append({
                        "type": "pom_dependency_change",
                        "file_path": file_path,
                        "message": change_note
                    })
            elif not impacts : # only show if no other impacts
                 structured_suggestions.append({
                    "type": "info",
                    "file_path": file_path,
                    "language": "maven_pom",
                    "message": f"No specific build dependency changes noted for this POM file."
                })

        elif language == 'other':
            if not impacts : # only show if no other impacts
                structured_suggestions.append({
                    "type": "info",
                    "file_path": file_path,
                    "message": f"No specific analysis findings for this file."
                })

    if not structured_suggestions:
        # This case should ideally be rare if the initial check for empty file_findings and overall_summary is handled
        structured_suggestions.append({"type": "info", "message": "No actionable suggestions were generated from the analysis. Please review the code manually."})

    return structured_suggestions
