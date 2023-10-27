🖥 Local Models
===============

To run gptme with local models, you need to install and run the [llama-cpp-python][llama-cpp-python] server. To ensure you get the most out of your hardware, make sure you build it with [the appropriate hardware acceleration][hwaccel].

For macOS, you can find detailed instructions [here][metal].

I recommend the WizardCoder-Python models.

[llama-cpp-python]: https://github.com/abetlen/llama-cpp-python
[hwaccel]: https://github.com/abetlen/llama-cpp-python#installation-with-hardware-acceleration
[metal]: https://github.com/abetlen/llama-cpp-python/blob/main/docs/install/macos.md

```sh
MODEL=~/ML/wizardcoder-python-13b-v1.0.Q4_K_M.gguf
poetry run python -m llama_cpp.server --model $MODEL --n_gpu_layers 1  # Use `--n_gpu_layer 1` if you have a M1/M2 chip

# Now, to use it:
export OPENAI_API_BASE="http://localhost:8000/v1"
gptme --llm local
```

