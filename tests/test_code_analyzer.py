import pytest
from src.code_analyzer import analyze_code_changes

# The placeholder test_example_code_analyzer is automatically removed by overwriting the file.

def test_analyze_code_changes_empty_pr_data(capsys):
    """Test with empty or invalid pr_data (None or missing 'files_changed')."""
    expected_empty_result = {
        'impact_areas': [],
        'reuse_suggestions': [],
        'solid_violations': []
    }

    # Test with None pr_data
    result_none = analyze_code_changes(None)
    assert result_none == expected_empty_result
    captured_none = capsys.readouterr()
    assert "Error: Invalid PR data provided for analysis." in captured_none.out

    # Test with pr_data missing 'files_changed' key
    result_no_files_key = analyze_code_changes({'title': 'Test PR'})
    assert result_no_files_key == expected_empty_result
    captured_no_files_key = capsys.readouterr() # capsys is fresh for this call within the same test
    assert "Error: Invalid PR data provided for analysis." in captured_no_files_key.out


def test_analyze_code_changes_no_files_changed():
    """Test with pr_data that has an empty list of files_changed."""
    pr_data = {
        'title': 'Test PR - No Files',
        'files_changed': [], # Empty list of files
        'diff': ''
    }
    result = analyze_code_changes(pr_data)

    assert result['impact_areas'] == []
    # Placeholder logic for reuse_suggestions depends on len(files_changed) > 1, so it should be empty.
    assert result['reuse_suggestions'] == []
    # SOLID violations placeholder is always added in the current implementation.
    assert result['solid_violations'] == ["Reminder: Review changes for adherence to SOLID principles (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion)."]

def test_analyze_code_changes_with_one_file_changed():
    """Test with pr_data having one file changed that includes a 'patch'."""
    pr_data = {
        'title': 'Test PR - One File',
        'files_changed': [
            {
                'filename': 'module_a/file1.py',
                'status': 'modified',
                'additions': 10,
                'deletions': 2,
                'patch': '@@ -1,1 +1,1 @@\n-old line\n+new line' # Patch is present
            }
        ],
        'diff': '...'
    }
    result = analyze_code_changes(pr_data)

    assert len(result['impact_areas']) == 1
    assert "File modified: module_a/file1.py (Status: modified)" in result['impact_areas'][0]
    # Placeholder logic for reuse_suggestions depends on len(files_changed) > 1.
    assert result['reuse_suggestions'] == []
    assert result['solid_violations'] == ["Reminder: Review changes for adherence to SOLID principles (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion)."]

def test_analyze_code_changes_with_multiple_files_changed():
    """Test with pr_data having multiple files changed, all including 'patch'."""
    pr_data = {
        'title': 'Test PR - Multiple Files',
        'files_changed': [
            {
                'filename': 'module_a/file1.py',
                'status': 'modified',
                'patch': '...' # Patch is present
            },
            {
                'filename': 'module_b/file2.py',
                'status': 'added',
                'patch': '...' # Patch is present
            }
        ],
        'diff': '...'
    }
    result = analyze_code_changes(pr_data)

    assert len(result['impact_areas']) == 2
    assert "File modified: module_a/file1.py (Status: modified)" in result['impact_areas'][0]
    assert "File modified: module_b/file2.py (Status: added)" in result['impact_areas'][1]

    # Placeholder logic for reuse_suggestions for multiple files.
    expected_reuse_suggestion = "Consider if there are common patterns across the changed files that could be abstracted."
    assert expected_reuse_suggestion in result['reuse_suggestions']

    assert result['solid_violations'] == ["Reminder: Review changes for adherence to SOLID principles (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion)."]

def test_analyze_code_changes_file_without_patch_key():
    """Test with a file_info entry that is missing the 'patch' key."""
    pr_data = {
        'title': 'Test PR - File No Patch Key',
        'files_changed': [
            {
                'filename': 'module_a/file_no_patch.py',
                'status': 'modified',
                # 'patch' key is intentionally missing here
            }
        ],
        'diff': '...'
    }
    result = analyze_code_changes(pr_data)

    # The code_analyzer.py checks `if 'patch' in file_info:`.
    # If the 'patch' key is missing, the file should not be added to 'impact_areas'.
    assert len(result['impact_areas']) == 0

    assert result['reuse_suggestions'] == [] # Only one file listed, though not processed for impact.
    assert result['solid_violations'] == ["Reminder: Review changes for adherence to SOLID principles (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion)."]

def test_analyze_code_changes_file_with_patch_key_none():
    """Test with a file_info entry that has a 'patch' key with a value of None."""
    pr_data = {
        'title': 'Test PR - File Patch is None',
        'files_changed': [
            {
                'filename': 'module_a/file_patch_none.py',
                'status': 'modified',
                'patch': None # 'patch' key is present but its value is None
            }
        ],
        'diff': '...'
    }
    result = analyze_code_changes(pr_data)

    # The code_analyzer.py checks `if 'patch' in file_info:`. This condition is true.
    # The content of the patch is not further validated in the current placeholder.
    # So, it should be added to impact_areas.
    assert len(result['impact_areas']) == 1
    assert "File modified: module_a/file_patch_none.py (Status: modified)" in result['impact_areas'][0]


    assert result['reuse_suggestions'] == []
    assert result['solid_violations'] == ["Reminder: Review changes for adherence to SOLID principles (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion)."]
