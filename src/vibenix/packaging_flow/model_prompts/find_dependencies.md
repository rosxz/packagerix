{% include 'snippets/prompt_intro.md' %}

Identify all the Nix dependencies necessary to package this project.

{% include 'snippets/project_info_section.md' %}

{% if common_dependency_files %}
Common dependency files found in the project:
```text
{{ common_dependency_files }}
```
{% endif %}

{% if project_file_tree %}
Project source file tree:
```text
{{ project_file_tree }}
```
{% endif %}
