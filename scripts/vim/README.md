# gptme.vim

A Vim plugin for [gptme][gptme] integration, allowing you to interact with gptme directly from your editor.

## Features

- Run gptme queries with context from your current buffer
- Automatically includes surrounding lines as context
- Results shown in a new buffer
- Configurable context size and key mappings

## Installation

The plugin assumes you have [gptme][gptme] installed and available in your PATH.

### Using a Plugin Manager

#### [vim-plug](https://github.com/junegunn/vim-plug)

Add this to your `.vimrc`:

    Plug 'ErikBjare/gptme', { 'rtp': 'scripts/vim' }

Then run:

    :PlugInstall

## Usage

The plugin provides both a command and a default mapping:

- `:Gptme` - Prompts for input and runs gptme with context
- `<Leader>g` - Same as `:Gptme`

When invoked, it will:
1. Prompt for your input
1. Get lines around cursor as context
1. Get file content as context
1. Run gptme with the prompt and context interactively in a new buffer

## Configuration

You can configure the following settings in your `.vimrc`:

### Context Lines

Set the number of context lines to include before and after cursor (default: 3):

    let g:gptme_context_lines = 5

### Key Mappings

Disable default key mappings:

    let g:gptme_no_mappings = 1

If you disable the default mappings, you can set your own:

    nnoremap <Leader>G :Gptme<CR>

## License

Same as Vim itself - see `:help license`

[gptme]: https://gptme.org
