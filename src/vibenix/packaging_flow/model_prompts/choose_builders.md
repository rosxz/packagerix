{% include 'snippets/prompt_intro.md' %}

Taking into account the project description below, choose the project builder(s) that should be used to package the following project.
For multi-language projects or projects with multiple components:
- Analyze the project information and source code with your available tools, to understand which language or framework builds the remaining components.

{% include 'snippets/project_info_section.md' %}

Here is the list of available builders:
{% for builder in available_builders %}
- {{ builder }}
{% endfor %}
