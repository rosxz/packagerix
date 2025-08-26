{% include 'snippets/prompt_intro.md' %}

Identify all the Nix dependencies necessary to package this project.
Use the tools at your disposal to find concrete dependencies instead of guessing them or their name in nixpkgs.

Your reply should follow the format:
```text
# Python
<dependency name 1>
<dependency name 2>
# Generic/Root
<dependency name 3>
(...)
```

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
