{% include 'snippets/prompt_intro.md' %}

Taking into account the project description below, choose the project builder(s) that are either required or greatly fit the packaging of the program.
For multi-language projects or projects with multiple components, it's likely that you should select more than one builder.

{% include 'snippets/project_info_section.md' %}

Search nixpkgs for examples of packages and look at project source with tool calls.

Here is the list of available builders:
{% for builder in available_builders %}
- {{ builder }}
{% endfor %}
