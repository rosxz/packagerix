{% include 'snippets/prompt_intro.md' %}

Taking into account the project description below, choose the most specific package builder(s) for this project.

{% include 'snippets/project_info_section.md' %}

**Builder Selection Rules:**
- Choose the **most specific builder** that matches the project's primary language/framework
- Only use `mkDerivation` as a fallback when no specialized builder exists, or when both are needed for separate components
- For mixed projects, choose all required builders and in order according to building sequence 

Available builders:
{% for builder in available_builders %}
- {{ builder }}
{% endfor %}

Use the tools at your disposal to construct your answer.
