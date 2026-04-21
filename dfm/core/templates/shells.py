"""Shell templates (Fish, Zsh)."""

from dfm.core.templates.types import Template


_FISH_CONTENT = """\
# Fish config - template by DFM

# Disable greeting
set -g fish_greeting ""

# Environment
set -gx EDITOR nvim
set -gx VISUAL nvim

# Path
fish_add_path ~/.local/bin

# Aliases
alias ls='ls --color=auto'
alias ll='ls -la'
alias la='ls -A'
alias grep='grep --color=auto'
alias vim='nvim'
alias ..='cd ..'
alias ...='cd ../..'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline --graph'
alias gd='git diff'

# System
alias update='sudo pacman -Syu'
alias cleanup='sudo pacman -Rns (pacman -Qdtq)'

# Prompt colors
set -g fish_color_command green
set -g fish_color_param normal
set -g fish_color_error red --bold
set -g fish_color_comment brblack
"""


_ZSHRC_CONTENT = """\
# Zsh config - template by DFM

# History
HISTSIZE=10000
SAVEHIST=10000
HISTFILE=~/.zsh_history
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_SPACE
setopt SHARE_HISTORY

# Completion
autoload -Uz compinit && compinit
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'

# Key bindings (vim mode)
bindkey -v
bindkey '^R' history-incremental-search-backward

# Environment
export EDITOR=nvim
export VISUAL=nvim
export PATH="$HOME/.local/bin:$PATH"

# Aliases
alias ls='ls --color=auto'
alias ll='ls -la'
alias la='ls -A'
alias grep='grep --color=auto'
alias vim='nvim'
alias ..='cd ..'
alias ...='cd ../..'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline --graph'

# Prompt
autoload -Uz vcs_info
precmd() { vcs_info }
zstyle ':vcs_info:git:*' formats '%b '
setopt PROMPT_SUBST
PROMPT='%F{blue}%~%f %F{green}${vcs_info_msg_0_}%f%# '
"""


SHELLS: list[Template] = [
    Template(
        name="fish-default",
        app_name="Fish",
        description="Fish shell config with useful aliases and prompt",
        category="Shells",
        config_path="~/.config/fish/config.fish",
        content=_FISH_CONTENT,
    ),
    Template(
        name="zshrc-default",
        app_name="Zsh",
        description="Zsh config with history, completions, and useful aliases",
        category="Shells",
        config_path="~/.zshrc",
        content=_ZSHRC_CONTENT,
    ),
]
