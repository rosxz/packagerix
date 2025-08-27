{% include 'snippets/prompt_intro.md' %}

Identify the Nix dependencies necessary to package this project with Nix.
Use the tools at your disposal to find concrete dependencies instead of guessing them or their name in nixpkgs.

Do not include any dependencies that are not in nixpkgs, and do not include any that does not seem necessary to explicitly add for packaging.

Your reply should follow the format:
```text
<dependency name 1>
<dependency name 2>
(...)
```

{% include 'snippets/project_info_section.md' %}

Here's the file contents for the project's {{ file_name }}:
```text
{{ file_content }}
```
