# Infinote

*Feel the spatial freedom in your notes.*

It's like a crossover between taking notes on paper and in vim, trying to keep the benefits of both, but also with some unique features not possible in either.

You have an infinitely expanding canvas on which you place notes. Each note is a separate markdown file.

## Instalation

Requires neovim to run. (I you have an existing `~/.config/nvim/init.vim` file, it will be sourced, it's not needed though.)

```bash
pipx install infinote-md --python $(which python3.11)
```

(If you don't have python3.11, use your default python3 instead, but note that 3.12 will cause some warnings while running. They can be safely ignored though.)

For LLM support, you also need to set your OpenAI API key:
```bash
echo "YOUR_OPENAI_API_KEY" > ~/.config/openai.token
```

For full functionality I also recommend these nvim plugins (but they are optional):
- 'ggandor/leap.nvim'
- 'madox2/vim-ai'
- 'ixru/nvim-markdown'
- 'MattesGroeger/vim-bookmarks'

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

To close the program, press `Alt-F4`.

## Shortcuts
- scroll with mouse wheel to zoom
- click to create a new box or to choose an existing one
- `<C-j>` - move to neighbor down
- `<C-k>` - move to neighbor up
- `<C-h>` - move to neighbor left
- `<C-l>` - move to neighbor right
- `<C-y>` - zoom down
- `<C-o>` - zoom up
- `<C-i>` - grow box
- `<C-u>` - shrink box
- `<C-g>` - **G**ive birth to a child box
- `<C-t>` - **T**eleport using leap.nvim plugin (must be installed)
- `<C-f>` - **F**ocus view on the current text box
- `<C-s>` - **S**ummon GPT into a child text box (madox2/vim-ai must be installed)
- `<C-w>` - delete box
- `<C-d>` - **D**etach a child from it's parent, to make it independent
- `<C-b>` - **B**ookmark jump - when in bookmarks window, jump to location of bookmark under cursor (vim-bookmarks plugin must be installed)
- `<A-Left>` - jump back
- `<A-Right>` - jump forward

## Customization

Edit the `config.py` file. When running infinote, it will output the exact path to this config file.

(Note that upgrading with pipx will overwrite this file.)

## Troubleshooting

If program hangs during opening, check if vim can open your .md notes. There may be some lingering swap files that you'll need to delete (usually in `~/.local/state/nvim/swap`). Or simply copy your note folder to a new location and see if it opens there.

If with python3.12 you get `Exception ignored in [...] RuntimeError: Event loop is closed` while closing, don't worry, it doesn't pose a problem. I just couldn't figure out how to get rid of that warning (seems like some PySide6 weirdness). If it bothers you, install python3.11 and reinstall infinote using the command in the installation section.