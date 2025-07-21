import pytest
from src.suggestion_generator import generate_suggestions
from src.code_analyzer import (
    ANALYSIS_PYTHON_AST, ANALYSIS_FLAKE8, ANALYSIS_JAVA_CHECKSTYLE,
    ANALYSIS_JAVA_PARSER, ANALYSIS_SECURITY_KEYWORD_SCAN,
    ANALYSIS_PYTHON_TEST_STUB_GEN, ANALYSIS_MAVEN_POM, ANALYSIS_JAVA_TEST_STUB_GEN
)

def test_generate_suggestions_input_none(capsys):
    result_none = generate_suggestions(None)
    assert result_none == [{"type": "error", "message": "No analysis results provided."}]
    captured_none = capsys.readouterr()
    assert "Error: No analysis results provided for suggestion generation." in captured_none.out

def test_generate_suggestions_completely_empty_analysis():
    analysis_results = {
        'overall_summary': {
            'reuse_suggestions': [], 'solid_violations': [], 'general_security_reminders': []
        },
        'file_specific_findings': []
    }
    result = generate_suggestions(analysis_results)
    assert result == [{"type": "info", "message": "No specific suggestions based on the current analysis. General best practices still apply."}]

def test_generate_suggestions_only_overall_summary():
    analysis_results = {
        'overall_summary': {
            'reuse_suggestions': ['Overall: Consider abstracting common utilities.'],
            'solid_violations': ['Overall: Check for SRP violations.'],
            'general_security_reminders': ['Overall: Remember to validate all inputs.']
        },
        'file_specific_findings': []
    }
    result = generate_suggestions(analysis_results)
    assert {"type": "general_summary", "category": "code_reuse", "message": "Overall: Consider abstracting common utilities."} in result
    assert {"type": "general_summary", "category": "design_pattern", "message": "Overall: Check for SRP violations."} in result
    assert {"type": "general_summary", "category": "security_reminder", "message": "Overall: Remember to validate all inputs."} in result
    assert len(result) == 3

def test_generate_suggestions_with_detailed_java_pom_and_python_stubs():
    mock_analysis = {
        'overall_summary': {
            'reuse_suggestions': ['Overall: Refactor common logic.'],
            'solid_violations': ['Overall: Adhere to SOLID.'],
            'general_security_reminders': ['Overall: Check inputs.']
        },
        'file_specific_findings': [
            {
                'file_path': 'src/utils.py', 'language': 'python',
                'impacts': ['Python file modified.'],
                'dependencies': ['Modified Function `util_func(arg1)` in src/utils.py. Review impacts.'],
                'tests_suggestions': ['Modified function `util_func(arg1)` detected. Review tests.'],
                'security_issues': [], 'linting_issues': [], 'python_definitions': [],
                'python_test_stubs': [{
                       'target_definition_name': 'my_new_func',
                       'target_definition_type': 'function',
                       'suggested_test_filename': 'tests/test_utils.py',
                       'stub_code': 'import unittest\n# ...etc...'
                   }]
            },
            {
                'file_path': 'com/example/MyClass.java', 'language': 'java',
                'impacts': ['Java file modified.'],
                'dependencies': ["Modified public method `getItems(String filter)` (declared line 15) in com/example/MyClass.java. Consider impact..."],
                'tests_suggestions': ["Modified public method `getItems(String filter)` (declared line 15) detected in com/example/MyClass.java. Recommend reviewing JUnit tests..."],
                'linting_issues': [{'line': 5, 'column': 1, 'code': 'JavadocPackage', 'message': 'Missing package-info.java file.', 'severity': 'info'}],
                'security_issues': ["Potential keyword 'secretPassword' found."],
                'java_definitions': [],
                'java_test_stubs': [{ # Added Java stub example
                    'target_definition_name': 'MyService',
                    'target_definition_type': 'Class',
                    'suggested_test_filename': 'com/example/MyServiceTest.java',
                    'stub_code': 'package com.example;\nimport org.junit.jupiter.api.Test;\n// ...etc...'
                }]
            },
            {
                'file_path': 'pom.xml', 'language': 'maven_pom',
                'impacts': ['pom.xml was modified.'],
                'build_dependency_changes': [
                    "Potentially 1 new/modified <dependency> block(s) added/changed in pom.xml.",
                ],
            },
            { 'file_path': 'README.md', 'language': 'other', 'impacts': ['Docs changed.'] }
        ]
    }
    suggestions = generate_suggestions(mock_analysis)
    assert any(s['type'] == 'general_summary' and s['category'] == 'code_reuse' and 'Overall: Refactor common logic.' in s['message'] for s in suggestions)
    assert any(s['type'] == 'general_summary' and s['category'] == 'design_pattern' and 'Overall: Adhere to SOLID.' in s['message'] for s in suggestions)
    assert any(s['type'] == 'general_summary' and s['category'] == 'security_reminder' and 'Overall: Check inputs.' in s['message'] for s in suggestions)
    assert any(s['type'] == 'file_marker' and s['file_path'] == 'src/utils.py' for s in suggestions)
    assert any(s['type'] == 'python_test_stub' for s in suggestions)
    assert any(s['type'] == 'file_marker' and s['file_path'] == 'com/example/MyClass.java' for s in suggestions)
    assert any(s['type'] == 'dependency_note' and 'Modified public method `getItems(String filter)`' in s['message'] for s in suggestions)
    assert any(s['type'] == 'test_suggestion' and 'Modified public method `getItems(String filter)`' in s['message'] for s in suggestions)
    assert any(s['type'] == 'linting' and 'Missing package-info.java file.' in s['message'] for s in suggestions)
    assert any(s['type'] == 'security_concern' and "Potential keyword 'secretPassword' found." in s['message'] for s in suggestions)
    assert any(s['type'] == 'java_test_stub' for s in suggestions)
    assert any(s['type'] == 'file_marker' and s['file_path'] == 'pom.xml' for s in suggestions)
    assert any(s['type'] == 'pom_dependency_change' and "Potentially 1 new/modified <dependency> block(s)" in s['message'] for s in suggestions)
    assert any(s['type'] == 'file_marker' and s['file_path'] == 'README.md' for s in suggestions)


def test_generate_suggestions_other_file_no_impact():
    analysis_results = { 'overall_summary': {}, 'file_specific_findings': [{'file_path': 'data.json', 'language': 'other', 'impacts': []}]}
    suggestions = generate_suggestions(analysis_results)
    assert any(s['type'] == 'file_marker' and s['file_path'] == 'data.json' for s in suggestions)
    assert any(s['type'] == 'info' and 'No specific analysis findings for this file.' in s['message'] for s in suggestions)
