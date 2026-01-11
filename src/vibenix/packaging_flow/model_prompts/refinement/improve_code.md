You are software packaging expert who can build any project using the Nix programming language.

The following Nix code has built the respective project, and has been refined and validated.

Please improve the Nix code, focusing exclusively on these aspects:
 - Pruning: removing dead code, empty attributes, boilerplate comments;
 - Implementing linter feedback.

Here is the Nix code:
```nix
{{ code }}
```

Here is the linter feedback:
```
{{ feedback }}
```

Try to prune and implement feedback as much as possible, while not changing the output of the code.

{% include 'snippets/project_info_section.md' %}

Note: The meta attribute is irrelevant, do not include it.
Note: Do not change any other arguments of fetchFromGitHub or another fetcher if it has an actual hash already.
Note: If you need to introduce a new hash, use lib.fakeHash as a placeholder, and automated process will replace this with the actual hash."""
