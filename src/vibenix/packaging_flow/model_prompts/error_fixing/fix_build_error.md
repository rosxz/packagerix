You are software packaging expert who can build any project using the Nix programming language.

Fix the error in the following Nix code.

Code:
```nix
{{ code }}
```

Error:
```
{{ error }}
```

{% if is_broken_log_output %}
**IMPORTANT: The build log output appears to be garbled. This is typically because the build system is outputting interactive elements (progress bars, ANSI codes, etc.) that don't work well in non-interactive environments.**
Prioritize fixing the log output.
Search the project source files for build configuration options, and documentation about non-interactive output, or command-line flags and environment variables that control output formatting.

{% endif %}
{% if is_dependency_build_error %}
**IMPORTANT: This appears to be a dependency build failure, not an error in your derivation.**

Common causes for dependency build failures:
1. Missing lock files (package-lock.json, Cargo.lock, etc.) - Check if the project needs these files
2. Wrong nixpkgs version or channel - You can't change this

**DO NOT:**
- Try to write derivations for the failing dependencies
- Attempt to patch or fix nixpkgs packages
- Get distracted from building the main project

{% endif %}
{% if is_syntax_error %}
**IMPORTANT: This appears to be an evaluation error, derived from syntactical mistakes.**
The causes for syntax errors are very often made before the location where the error is reported.

Example reference package:
```nix
{ lib
, stdenv
, fetchFromGitHub
, cmake
, pkg-config
, python3Packages
, qt6
}:

stdenv.mkDerivation rec {
  pname = "example-app";
  version = "1.0.0";

  src = fetchFromGitHub {
    owner = "example";
    repo = "example-app";
    rev = "v${version}";
    hash = "...";
  };

  nativeBuildInputs = [
    cmake
    pkg-config
    qt6.wrapQtAppsHook
  ];

  buildInputs = [
    qt6.qtbase
  ] ++ (with python3Packages; [
    requests
  ]);

  # Multi-line string with escaped special characters
  postPatch = ''
    # Escaped dollar sign
    substituteInPlace setup.py \
      --replace "''${OLD_VAR}" "new_value"
    
    # Escaped newline
    echo "Line 1''\nLine 2" > config.txt
    
    # Escaped apostrophes in multi-line string
    echo "Don'''t forget to escape" >> config.txt
  '';

  # Regular strings
  configureFlags = [
    "--enable-feature"
    "--with-path=${placeholder "out"}/lib"
  ];

  # Environment variable
  NIX_CFLAGS_COMPILE = "-O2 -DVERSION=\"${version}\"";
}
```

{% endif %}
{% if attempted_tool_calls %}
**The following tool calls have already been attempted without making progress. Consider trying different approaches:**
{% for call in attempted_tool_calls %}
- {{ call.function }}({% for key, value in call.arguments.items() %}{{ key }}="{{ value }}"{% if not loop.last %}, {% endif %}{% endfor %})
{% endfor %}

Try different tools, arguments, or entirely different approaches.

{% endif %}
{% include 'snippets/project_info_section.md' %}

Notes:
```md
{% include 'snippets/template_note_section.md' %}
```

- Nothing in the meta attribute has any impact on the build, ignore meta attributes.
- Do not alter the `src` attribute arguments (fetchFromGitHub) without good reason.
- Do not produce a flatpak, or docker container and do not use tools related to these technologies to produce your output.
- The package I am asking you to build is not in nixpkgs.

Your response needs to list the concrete changes you would make to the code to fix the error. Be specific.
