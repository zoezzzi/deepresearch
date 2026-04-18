SYSTEM_PROMPT = "You are a research summarization expert. Provide clear, concise summaries of research findings."

USER_PROMPT_TEMPLATE = """Research Intent: {{ intent }}

Search Results:
{{ formatted_results }}

Please provide:
1. A comprehensive summary of the findings related to the intent
2. A summary of the sources used (with URLs)
3. Any important notices or caveats about the information

Format your response clearly with these three sections."""
