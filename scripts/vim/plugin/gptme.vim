" gptme.vim - gptme integration for Vim
" Maintainer: Erik Bjäreholt
" Version: 0.1

if exists('g:loaded_gptme')
    finish
endif
let g:loaded_gptme = 1

" Default settings
if !exists('g:gptme_context_lines')
    let g:gptme_context_lines = 3
endif

function! s:gptme() range
    " Check if range was given (visual selection)
    let l:has_range = a:firstline != a:lastline

    if l:has_range
        " Get visually selected lines
        let l:context = getline(a:firstline, a:lastline)
    else
        " Get context around cursor
        let l:current_line = line('.')
        let l:start_line = max([1, l:current_line - g:gptme_context_lines])
        let l:end_line = min([line('$'), l:current_line + g:gptme_context_lines])
        let l:context = getline(l:start_line, l:end_line)
    endif

    let l:context_text = join(l:context, "\n")
    let l:ft = empty(&filetype) ? '' : &filetype
    let l:filename = expand('%:p')

    " Now get input from user
    let l:input = input('gptme prompt: ')
    if empty(l:input)
        return
    endif

    " Build the prompt with proper escaping
    let l:prompt = l:input . " at:\n```" . l:ft . "\n" . l:context_text . "\n```"

    " Build the command with proper shell escaping
    let l:cmd = 'gptme ' . shellescape(l:prompt) . ' ' . shellescape(l:filename)

    " Debug: Show command (optional)
    " echom "Command: " . l:cmd

    " Open terminal in a new window
    vertical new
    file gptme

    " Use appropriate terminal function based on Vim/Neovim
    if has('nvim')
        call termopen(l:cmd)
        " Auto-enter insert mode in terminal (Neovim)
        startinsert
    else
        call term_start(l:cmd, {'curwin': 1})
    endif
endfunction

" Map it to <Leader>g (usually \g) unless user disabled default mappings
if !exists('g:gptme_no_mappings')
    nnoremap <Leader>g :call <SID>gptme()<CR>
    " Add visual mode mapping
    vnoremap <Leader>g :call <SID>gptme()<CR>
endif

" Command interface (note the capital G)
command! -range Gptme <line1>,<line2>call <SID>gptme()
