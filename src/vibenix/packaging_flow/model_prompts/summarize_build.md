{% include 'snippets/prompt_intro.md' %}

Write brief step-by-step instructions to the build process, naming the essential components involved (Python, Npm, Rust) and the respective build tools.
Use the tools at your disposal to construct your answer, especially inspect the project source.

Here is a summary of the project's page:
```text
{{ summary }}
```

- You should not include any irrelevant introductory text, such as "Here is a ... :", just the instructions themselves.
- Try to be as accurate as possible, avoiding vague statements like "likely present in ...", by means of your tools and the provided project summary.
- Inspect build tool scripts and files to identify other required builder tools (e.g. electron). Ignore regular project dependencies.

Your response should be complete, but to the point, like so:
```text
1. Verify <build tool> version is compatible with <version>, specified in <file>.
2. Run `<build tool> build:frontend` to build the frontend. This will run <framework tool>, so make sure it is installed.
3. Run `<build tool 2> install` to install <framework> dependencies.
(...)
```
