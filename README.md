# Packagerix - AI assistant for nix packaging

The elevator pitch for this project is that you give it the URL of a GitHub project,
and it starts from a template and iteratively improves on that until it finally succeeds (or fails) to build the package.

### Disclaimer

---

🚧 Can only build at most 20 % of all unseen things so far. 🚧

---

### My plans with this work

I want to publish a paper based on this work, so if you're interested in that or want to collaborate on related work send me a message.

I could also imagine providing this functionality as a hosted service to customers, so if you are curious about that, please send me an email as well.

### How to run this

To run the textual UI use:
```
nix develop -c python -m packagerix
```

You will be asked to pick a model and also provide an API key if requried.
In terms of local models right now I recommend `qwen2.5-coder:32b`, which works well as long as the input stays short enough, but needs a hair more than 24GB of VRAM to fit fully into VRAM. The 8b models I tried so far seem to struggle too much with hashes and function calling.
All the local models I have tried struggle with inputs that are longer than `12000` characters, which some github pages exceed.
In terms of hosted models, `claude-3-5-haiku-20241022` for example, can cope with longer prompts as well.
It's what I am targeting as of now. So far, I don't think you need a better model than that for packaging.
