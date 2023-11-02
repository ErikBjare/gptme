Finetuning
==========

NOTE: this document is a work in progress!

This document aims to provide a step-by-step guide to finetuning a model on conversations from gptme using the Hugging Face transformers library.

The goal of fine-tuning a model for gptme is to:

 - Teach the tools available in gptme
 - Update out-of-date knowledge and conventions
 - Improve its ability to recover from errors


## Step 1: Gather the data

To fine-tune we need something to fine-tune on.

We will fine-tune on our own conversation history, combined with a subset of the [OpenAssistant dataset][oa-dataset] to extend the training data with relevant examples.

We collect our own conversation history by running the following command:

```bash
./train/collect.py --model "HuggingFaceH4/zephyr-7b-beta"  # or whatever model you intend to fine-tune
```

This will create files `train.csv` and `train.jsonl` in the `train` directory.


## Step 2: Prepare the data

We need to prepare the data for fine-tuning. This involves:

 - Extend the data with examples from the OpenAssistant dataset
 - Splitting the data into train and validation sets
   - We might want to make sure that the validation set is comprised of examples from gptme, and not from the OpenAssistant dataset.

TODO...


## Step 3: Fine-tune the model


Options:

 - [axolotl][axolotl]
   - Does it support Mistral? (and by extension Zephyr)
 - [Hugging Face transformers][hf-transformers]
   - [Examples for Llama2][llama-finetuning] by Meta
 - [OpenPipe][openpipe]?
   - Looks interesting, but not sure if it's relevant for us.

TODO..

## Model suggestions

 - HuggingFaceH4/zephyr-7b-beta
 - teknium/Replit-v2-CodeInstruct-3B 
   - I had issues with this one on M2, but would be good to have some 3B model as an example used in testing/debug.

[oa-datasets]: https://projects.laion.ai/Open-Assistant/docs/data/datasets
[axolotl]: https://github.com/OpenAccess-AI-Collective/axolotl
[llama-finetuning]: https://ai.meta.com/llama/get-started/#fine-tuning
