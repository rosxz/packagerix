# Vibenix - AI assistant for nix packaging

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
nix develop -c python -m vibenix
```

You will be asked to pick a model and also provide an API key if requried.

Currently, only Gemini models have working tool calling support in this repo right now. We recommend using `gemini/gemini-2.5-pro` as the default model.
While `claude-3-5-haiku-20241022` can cope with longer prompts, that as of now missing tool calling support on our end prevents them from working here.
We would like to target local models in the future, but we do not have working tool calling support for them yet either.
All the local models we have tried so far also struggle with inputs that are longer than `12000` characters, which some of our prompts might exceed.
Our assumption is that those modles struggle with complex tasks like this when relying on RoPE to extend their native context windows.


When tool calling is fixed, `qwen2.5-coder:32b` might work well as long as the input stays short enough, but needs a hair more than 24GB of VRAM to fit fully into VRAM. The 8b models I tried so far seem to struggle too much with hashes and function calling.
