{% include 'snippets/prompt_intro.md' %}

Your task is to implement changes to the following packaging code:

Code:
```nix
{{ code }}
```

Changes to implement:
```txt
{{ changes }}
```

Refrain from making any other modifications or additions beyond what is specified in the changes above.

To perform each change to the code, use the text editor tools: {{ edit_tools }}.

Refrain from making more than 10 tool calls in total. If you haven't implemented all requested changes after 10 tool calls, refrain from making more edits and end your response.
