# gptme.vim

A Vim plugin for [gptme](https://gptme.org) integration, allowing you to interact with gptme directly from your editor.

## Features

- Run gptme queries with context from your current buffer
- Automatically includes surrounding lines as context
- Results shown in a new buffer
- Configurable context size and key mappings

## Installation

### Using a Plugin Manager

#### [vim-plug](https://github.com/junegunn/vim-plug)

Add this to your `.vimrc`:

    Plug 'ErikBjare/gptme', { 'rtp': 'scripts/vim' }

Then run:

    :PlugInstall

### Manual Installation

Copy the contents of this directory to your ~/.vim directory:

    cp -r plugin doc ~/.vim/

## Usage

The plugin provides both a command and a default mapping:

- `:gptme` - Prompts for input and runs gptme with context
- `<Leader>g` - Same as :gptme (usually `\g`)

When invoked, it will:
1. Prompt for your input
2. Get context from around your cursor
3. Run gptme with both inputs
4. Show the result in a new buffer

## Configuration

You can configure the following settings in your `.vimrc`:
### Context Lines

Set the number of context lines to include before and after cursor (default: 3):

    let g:gptme_context_lines = 5

### Key Mappings

Disable default key mappings:

    let g:gptme_no_mappings = 1

If you disable the default mappings, you can set your own:

    nnoremap <Leader>G :gptme<CR>

## License

Same as Vim itself - see `:help license`
