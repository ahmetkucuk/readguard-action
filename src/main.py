import os
import sys
import json
import hashlib
import secrets
import logging
from github_client import GithubClient
from llm_client import LLMClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CHECK_NAME = "ReadGuard Verification"

def get_required_env(key):
    val = os.getenv(key)
    if not val:
        logger.error(f"Missing required environment variable: {key}")
        sys.exit(1)
    return val

def compute_hash(answer, salt):
    # Normalize answer to uppercase
    answer = answer.strip().upper()
    data = f"{answer}:{salt}"
    return hashlib.sha256(data.encode()).hexdigest()

def create_hidden_metadata(data):
    # Embed json in an HTML comment so it's hidden from the user but readable by the bot
    json_str = json.dumps(data)
    return f"<!-- readguard_meta: {json_str} -->"

def extract_metadata(text):
    match = re.search(r'<!-- readguard_meta: (.*?) -->', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None

import re

def run_generate_mode(gh_client, llm_client, inputs):
    logger.info("Starting Generate Mode")
    
    # 1. Get Diff
    files = gh_client.get_pr_diff()
    diff_text = ""
    for file in files:
        # Limit to reasonable size to avoid context window issues
        # In a real app we would be smarter about selecting relevant files
        if file.patch:
            diff_text += f"File: {file.filename}\n{file.patch}\n\n"
    
    if not diff_text:
        logger.info("No diff found or no changes. Exiting.")
        return

    # 2. Generate Question
    logger.info("Querying LLM...")
    q_data = llm_client.generate_question(
        diff_text[:10000],  # Simple truncation
        difficulty=inputs.get('difficulty', 'medium'),
        system_prompt=inputs.get('system_prompt'),
        custom_instructions=inputs.get('custom_instructions')
    )
    
    if not q_data:
        logger.error("Failed to generate question.")
        sys.exit(1)

    # 3. Prepare Verification Data
    salt = secrets.token_hex(16)
    correct_hash = compute_hash(q_data['correct_answer'], salt)
    
    metadata = {
        "salt": salt,
        "hash": correct_hash,
        "mode": "quiz"
    }
    
    # 4. Post Comment
    body = f"""
## 🛡️ ReadGuard Verification
    
**Proof-of-Reading Required**
The following question has been generated based on the changes in this PR.

**{q_data['question']}**

- **A)** {q_data['options']['A']}
- **B)** {q_data['options']['B']}
- **C)** {q_data['options']['C']}

Reply with `/answer A`, `/answer B`, or `/answer C` to unlock the merge.

{create_hidden_metadata(metadata)}
"""
    gh_client.post_comment(body)
    
    # 5. Create Failed Check
    head_sha = gh_client.pr.head.sha
    gh_client.create_check_run(
        name=CHECK_NAME,
        head_sha=head_sha,
        status="completed",
        conclusion="action_required",
        output={
            "title": "ReadGuard Quiz",
            "summary": "Please answer the quiz in the PR comments to proceed."
        }
    )
    logger.info("Quiz posted and check run created.")

def run_verify_mode(gh_client):
    logger.info("Starting Verify Mode")
    
    # 1. Get User Answer from Comment
    event_path = os.getenv('GITHUB_EVENT_PATH')
    with open(event_path, 'r') as f:
        event = json.load(f)
    
    comment_body = event['comment']['body'].strip()
    match = re.match(r'/answer\s+([a-cA-C])', comment_body)
    
    if not match:
        logger.info("Comment does not contain a valid answer format. Ignoring.")
        sys.exit(0)
        
    user_answer = match.group(1).upper()
    logger.info(f"Received answer: {user_answer}")
    
    # 2. Find the Bot's Quiz Comment
    # We iterate backwards to find the most recent quiz
    comments = gh_client.get_bot_comments()
    quiz_comment = None
    metadata = None
    
    for comment in reversed(list(comments)):
        # Check if it is from the bot (github-actions[bot] or similar) 
        # But easier to just check for our metadata
        meta = extract_metadata(comment.body)
        if meta and meta.get('mode') == 'quiz':
            quiz_comment = comment
            metadata = meta
            break
            
    if not metadata:
        logger.error("Could not find a ReadGuard quiz comment.")
        sys.exit(1)
        
    # 3. Verify Hash
    expected_hash = metadata['hash']
    salt = metadata['salt']
    
    computed_hash = compute_hash(user_answer, salt)
    
    head_sha = gh_client.pr.head.sha
    
    if computed_hash == expected_hash:
        logger.info("Answer Correct!")
        # 4. Success
        gh_client.post_comment(f"✅ Correct! The answer was **{user_answer}**. verification successful.")
        
        # Update check run
        # We need to find the specific check run or just create a new passing one for the commit
        # Creating a new one with the same name usually overrides or adds to it, which is fine
        gh_client.create_check_run(
            name=CHECK_NAME,
            head_sha=head_sha,
            status="completed",
            conclusion="success",
            output={
                "title": "ReadGuard Verified",
                "summary": "Developer successfully answered the proof-of-reading quiz."
            }
        )
    else:
        logger.info("Answer Incorrect.")
        # 5. Failure
        gh_client.post_comment(f"❌ Incorrect. Please try again.")
        # Ensure check remains failed
        gh_client.create_check_run(
            name=CHECK_NAME,
            head_sha=head_sha,
            status="completed",
            conclusion="failure",
            output={
                "title": "ReadGuard Failed",
                "summary": "Incorrect answer provided."
            }
        )

def main():
    mode = os.getenv('INPUT_MODE', 'generate')
    github_token = get_required_env('INPUT_GITHUB_TOKEN')
    
    gh_client = GithubClient(github_token)
    
    if mode == 'generate':
        api_key = get_required_env('INPUT_API_KEY')
        provider = os.getenv('INPUT_PROVIDER', 'openai')
        model = os.getenv('INPUT_MODEL') # Can be None, client handles default
        inputs = {
            'difficulty': os.getenv('INPUT_DIFFICULTY', 'medium'),
            'system_prompt': os.getenv('INPUT_SYSTEM_PROMPT'),
            'custom_instructions': os.getenv('INPUT_CUSTOM_INSTRUCTIONS')
        }
        
        llm_client = LLMClient(provider, api_key, model)
        run_generate_mode(gh_client, llm_client, inputs)
        
    elif mode == 'verify':
        run_verify_mode(gh_client)
        
    else:
        logger.error(f"Invalid mode: {mode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
