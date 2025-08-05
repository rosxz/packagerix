# Vibenix - AI assistant for nix packaging

The elevator pitch for this project is that you give it the URL of a GitHub project,
and it starts from a template and iteratively improves on that until it finally succeeds (or fails) to build the package.

### Disclaimer

---

🚧 Can only build at most 38 % (14 % verified functionally correct) of all unseen things so far. 🚧

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

Models we have tested to perform well are our default model `gemini-2.5-flash` (38 %),
`claude-3-5-haiku-20241022` (32 %) and `o3-mini-2025-01-31` (26 %).
Numbers in prarenthesis are raw sucess rate before validation. Manually validated success rate with `gemini-2.5-flash` is about half, at 14 %.
We would like to target local models in the future, but we are still working on issues to get that working (https://github.com/mschwaig/vibenix/issues/42).
Right now vibenix tries to stay within 32k context size, which with `32b` class models results in a bit more than 32GB VRAM usage.
