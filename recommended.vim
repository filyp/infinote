

call plug#begin('~/.vim/plugged')
Plug 'ggandor/leap.nvim'
Plug 'madox2/vim-ai'
Plug 'MattesGroeger/vim-bookmarks'
Plug 'ixru/nvim-markdown'
call plug#end()

let g:bookmark_save_per_working_dir = 1
let g:bookmark_highlight_lines = 1
let g:bookmark_manage_per_buffer = 1


""""""""""""""""""""""""""""
" optional

" " autowrite:
" autocmd TextChanged,TextChangedI <buffer> silent write

" " disable enter mapping
" map <Plug> <Plug>Markdown_FollowLink