import os
import hashlib
import json
import re
from github import Github

class GithubClient:
    def __init__(self, token):
        self.g = Github(token)
        self.repo = self._get_repo()
        self.pr = self._get_pr()

    def _get_repo(self):
        repo_name = os.getenv('GITHUB_REPOSITORY')
        if not repo_name:
            raise ValueError("GITHUB_REPOSITORY environment variable not set")
        return self.g.get_repo(repo_name)

    def _get_pr(self):
        event_path = os.getenv('GITHUB_EVENT_PATH')
        if not event_path:
            return None
            
        with open(event_path, 'r') as f:
            event_data = json.load(f)
        
        # Handle pull_request event
        if 'pull_request' in event_data:
            return self.repo.get_pull(event_data['pull_request']['number'])
        
        # Handle issue_comment event (on a PR)
        if 'issue' in event_data and 'pull_request' in event_data['issue']:
            return self.repo.get_pull(event_data['issue']['number'])
            
        return None

    def get_pr_diff(self):
        if not self.pr:
            raise ValueError("Not running in a PR context")
        # Get the diff of the PR
        # We might need to handle large diffs, but for now take the whole thing
        # In a real scenario we'd probably want to filter for meaningful changes
        return self.pr.get_files()

    def post_comment(self, body):
        if not self.pr:
             raise ValueError("Not running in a PR context")
        self.pr.create_issue_comment(body)

    def get_bot_comments(self):
        if not self.pr:
             raise ValueError("Not running in a PR context")
        # In a real action we'd verify the user ID, but checking the body for our metadata is a good start
        return self.pr.get_issue_comments()

    def create_check_run(self, name, head_sha, status, conclusion=None, output=None):
        # status: queued, in_progress, completed
        # conclusion: success, failure, neutral, cancelled, skipped, timed_out, action_required
        kwargs = {
            "name": name,
            "head_sha": head_sha,
            "status": status
        }
        if conclusion:
            kwargs["conclusion"] = conclusion
        if output:
            kwargs["output"] = output
            
        return self.repo.create_check_run(**kwargs)
        
    def update_check_run(self, check_run_id, status, conclusion=None, output=None):
         # This needs the check run ID, which might be tricky to persistence without a server.
         # Alternatively, we can find the check run by name.
         pass # Simplified for now, we might just create new ones or find the latest by name

    def find_latest_check_run(self, name, head_sha):
        runs = self.repo.get_check_runs(check_name=name, commit=self.repo.get_commit(head_sha))
        if runs.totalCount > 0:
            return runs[0]
        return None
