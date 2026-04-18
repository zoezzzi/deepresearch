SYSTEM_PROMPT = "You are a research planning expert. Generate a structured research plan with clear, actionable tasks."

USER_PROMPT_TEMPLATE = """Generate a research plan for the following topic:

Topic: {{ topic }}
Description: {{ description or 'No additional description provided' }}

Please generate a list of {{ task_count | default(5) }} research tasks. For each task, provide:
- title: A clear, concise title for the task
- intent: The purpose or goal of this task
- query: A specific search query to use for this task
- order: The sequence number (starting from 1)

Format your response as a valid JSON array of objects with these fields."""
