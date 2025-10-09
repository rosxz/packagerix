{% include 'snippets/prompt_intro.md' %}

Please fix the syntax errors (parsing) present in the following Nix code.

Code:
```nix
{{ code }}
```

Error:
```
{{ error }}
```

Abstain from making any other changes unrelated to syntactical mistakes on the Nix expression. 
Remember that:
- Strings are ONLY defined with quotation marks (")
- Multi-line strings are ONLY defined with double apostrophes ('')
- Double apostrophes ('') in multi-line strings are escaped with a single apostrophe ('), e.g. ''test\n'''var'' is a single multi-line string with an escaped apostrophe.
- In multi-line strings, dollar signs ($), dollar-curly (${), line-feed (\n), and carriage-return (\n) must be escaped with double apostrophes (''). For example, ''test\n''$var'' is a single multi-line string with escaped dollar.
- For the remaining cases, special characters are usually escaped with a backslash (\).

**IMPORTANT**: For each change to the code, use the `str_replace` tool.
Your final reply should only contain a very brief explanation of all the changes made with the `str_replace` tool, NOT the fully updated code.
