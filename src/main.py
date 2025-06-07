import argparse
# from .pr_parser import get_pr_details
# from .code_analyzer import analyze_code_changes
# from .suggestion_generator import generate_suggestions

# To allow running this as a script from the root directory (e.g., python -m src.main)
# and also to handle potential imports if this were part of a larger package.
if __package__ is None or __package__ == '':
    # When run as a script, adjust path to import siblings
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent)) # Appends the root directory (parent of src)
    from src.pr_parser import get_pr_details
    from src.code_analyzer import analyze_code_changes
    from src.suggestion_generator import generate_suggestions
else:
    # When imported as part of a package
    from .pr_parser import get_pr_details
    from .code_analyzer import analyze_code_changes
    from .suggestion_generator import generate_suggestions

def main():
    parser = argparse.ArgumentParser(description="AI Agent for PR Review")
    parser.add_argument("pr_url", help="The URL of the GitHub Pull Request to review.")

    args = parser.parse_args()
    pr_url = args.pr_url

    print(f"Starting review for PR: {pr_url}")

    # 1. Fetch PR Details
    print("\nFetching PR details...")
    pr_data = get_pr_details(pr_url)
    if not pr_data:
        print("Failed to fetch PR details. Exiting.")
        return

    print(f"Successfully fetched details for PR: {pr_data.get('title', 'N/A')}")
    print(f"Author: {pr_data.get('author', 'N/A')}")
    print(f"Files changed: {len(pr_data.get('files_changed', []))}")

    # 2. Analyze Code Changes
    print("\nAnalyzing code changes...")
    analysis_results = analyze_code_changes(pr_data)
    if not analysis_results: # analysis_results can be an empty dict with lists, so it's not "Falsy"
        # It's better to check if essential parts of analysis are missing,
        # but for now, the analyze_code_changes returns a dict that is never None
        # and prints its own error if input pr_data is bad.
        # So, this check might not be strictly necessary if analyze_code_changes handles its errors well.
        pass # Assuming analyze_code_changes prints errors and returns a valid (even if empty) structure.

    print("Code analysis complete.") # This will print even if analysis_results is "empty" but valid.

    # 3. Generate Suggestions
    print("\nGenerating suggestions...")
    suggestions = generate_suggestions(analysis_results)
    if not suggestions:
        # generate_suggestions is designed to return a default "No specific suggestions" message
        # if nothing else is generated, so this condition might only be true if it explicitly returns an empty list on error.
        # The current implementation of generate_suggestions returns a default message, so it's rarely empty.
        print("No suggestions were generated, or suggestion generation failed.")
        # We might want to reconsider if we want to exit here or still show the "no suggestions" message.
        # For now, let's allow it to proceed to display whatever generate_suggestions returned.
        # return # Optional: exit if truly no suggestions (even default ones) are made.

    print("Suggestions generated.")

    # 4. Display Suggestions
    print("\n--- PR Review Suggestions ---")
    if pr_data.get('title'):
        print(f"PR Title: {pr_data['title']}")
    if pr_data.get('html_url'):
        print(f"PR URL: {pr_data['html_url']}")

    print("\nSuggestions:")
    if suggestions: # Ensure suggestions list is not empty before iterating
        for i, suggestion in enumerate(suggestions, 1):
            print(f"{i}. {suggestion}")
    else:
        print("No suggestions available to display.") # Fallback message

    print("\n--- End of Review ---")

if __name__ == "__main__":
    # Note: To run this from the project root, use:
    # python -m src.main <your_pr_url>
    # Make sure 'requests' is installed (pip install -r requirements.txt)
    #
    # Example (requires a live PR URL):
    # python -m src.main https://github.com/octocat/Spoon-Knife/pull/3
    #
    # Since we can't make live calls in this environment easily for testing the full flow,
    # the actual execution with a real URL should be done in a local dev environment.
    # For now, this structure sets up the CLI.

    # A small adjustment to the sys.path logic for robustness if __file__ is not absolute
    if __package__ is None or __package__ == '':
        current_file_path = Path(__file__).resolve()
        project_root = current_file_path.parent.parent
        if str(project_root) not in sys.path:
            sys.path.append(str(project_root))

        # Re-import with adjusted path if necessary (for the script execution case)
        # This is a bit redundant if the first block already handled it, but ensures src.module works.
        from src.pr_parser import get_pr_details
        from src.code_analyzer import analyze_code_changes
        from src.suggestion_generator import generate_suggestions

    main()
