# Packagerix - AI assistant for nix packaging

The elevator pitch for this project is that you give it the URL of a GitHub project,
and it starts from a template and iteratively improves on it until it finally succeeds (or fails)
to build the package, at which point we might be able to still get it over the finish line with manual intervention.

### Disclaimer

---

🚧 This is a very ealy prototype that does not successfully loop yet, it only does the first iteration. 🚧

---

### My plans with this work

I want to publish a paper based on this work, so if you're interested in that or want to collaborate on related work send me a message.

I could also imagine providing this functionality as a hosted service to customers, so if you are curious about that, please send me an email as well.

### How to run this

To run the terminal UI use:
```
nix develop -c python -m app.packagerix
```

You have to set an appropriate model in the `flake.nix` file.
In terms of local models right now I recommend `qwen2.5-coder`, which works well as long as the input stays short enough.
All the local models I have tried struggle with inputs that are longer than `12000` characters, which some github pages exceed.
In terms of hosted models, Claude Haiku for example, can cope with longer prompts as well. I have not tried other hosted models recently.
