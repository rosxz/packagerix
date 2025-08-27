{% include 'snippets/prompt_intro.md' %}

Identify 3 project files most relevant for identifying required dependencies to package this project.
Select less files in case there aren't enough relevant ones.

{% if project_file_tree %}
Project source file tree:
```text
{{ project_file_tree }}
```
{% endif %}

{% include 'snippets/project_info_section.md' %}
