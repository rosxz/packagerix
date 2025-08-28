{% include 'snippets/prompt_intro.md' %}

Compare the chosen Nix packaging template with the builder helper combinations available and their packages.
Replace or keep the template builder and related options in accordance with your findings.

{% include 'snippets/project_info_section.md' %}

Here is the chosen Nix packaging template:
```nix
{{ initial_code }}
```

Here is information regarding builder combinations and packages using them:
```text
{{ builder_combinations_info }}
```

Consult the documentation for the main package builder considered, and especially so if the template's builder differs.

Use your available tools to analyze the project source and builder combinations packages.
Your response should be a valid Nix expression similar in structure to the template provided, wrapped like so:
```nix
...
```
Do not change the version, rev, and hash attributes or other details that are otherwise unrelated to the packaging template or builder choice.
Do not add dependencies or otherwise modify the package beyond what is necessary for the template structure or builder change.
