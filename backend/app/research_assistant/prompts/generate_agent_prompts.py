SYSTEM_PROMPT = "You are a research report generation expert. Create comprehensive, well-structured research reports in Markdown format."

USER_PROMPT_TEMPLATE = """Generate a comprehensive research report on the following topic:

Topic: {{ topic }}

Research Task Summaries:
{{ task_summaries }}

Please create a well-structured Markdown report that includes:
1. Title page with topic
2. Table of contents
3. Executive summary
4. Main findings organized by sections
5. Conclusion
6. References section with all sources

Make the report professional, comprehensive, and easy to read."""
