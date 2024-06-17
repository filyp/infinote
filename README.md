# Infinote

*Feel the spatial freedom in your notes.*

It's like a crossover between taking notes on paper and in vim, trying to keep the benefits of both, but also with some unique features not possible in either.

You have an infinitely expanding canvas on which you place notes. Each note has its own neovim buffer, and all your neovim config from your `~/.config/nvim/init.vim` will work. The notes will be saved as plain markdown files.

## Instalation

Requires neovim to run. I you have existing `init.vim` file, it will be sourced.

```bash
pipx install infinote-md
```


I also recommend these vim plugins (but they are optional):
```
Plug 'ggandor/leap.nvim'
Plug 'ixru/nvim-markdown'
Plug 'MattesGroeger/vim-bookmarks'
```

## Runninng

```
infinote PATH_TO_WORKSPACE GROUP
```

(Necessary folders will be created.)

F.e.:
```
infinote ~/cloud/notes/astrophysics scratchpad
```

Here `~/cloud/notes/astrophysics` is the workspace name, and `scratchpad` is the group name. Every group will have a different color. All the groups from the chosen workspace will be shown, but you will add boxes only to the chosen group. If you don't specify the group name, it will be set to the current month in the form: yy.MM, f.e. `24.07`, so each month will be a different group.

## Shortcuts
- scroll with mouse wheel to zoom
- click to create a new box or to choose an existing one
- `<A-j>` - move to neighbor down
- `<A-k>` - move to neighbor up
- `<A-h>` - move to neighbor left
- `<A-l>` - move to neighbor right
- `<M-A-l>` - make a new child of the current text box, to the right
- `<A-y>` - zoom down
- `<A-o>` - zoom up
- `<A-u>` - grow box
- `<A-i>` - shrink box
- `<C-o>` - jump back
- `<C-i>` - jump forward
- `,c` - center the view on current box
- `,m` - maximize the view on current box (zoom out as much as possible, while keeping the current box in view)
- `,b` - when in bookmarks window, jump to location of bookmark under cursor
    - requires 'MattesGroeger/vim-bookmarks' installed
- `,h` - hop to any text using leap plugin
    - requires 'ggandor/leap.nvim' installed

## Customization

Edit the `config.py` file. When running infinote, it will output the exact path to this config file.

(Note that upgrading with pipx will overwrite this file.)

## Troubleshooting

If program hangs during opening, check if vim can open your .md notes. There may be some lingering swap files that you'll need to delete. Or simply copy your note folder to a new location and see if it opens there.
