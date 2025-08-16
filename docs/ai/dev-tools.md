# AI Developer tools

## Code completion, chat with code

### continue.dev

> Continue is the leading open-source AI code assistant. You can connect any models and any context to build custom autocomplete and chat experiences inside VS Code and JetBrains

https://github.com/continuedev/continue

### Twinny (VSCode plugin)

> The most no-nonsense locally hosted (or API hosted) AI code completion plugin for Visual Studio Code, like GitHub Copilot but 100% free and 100% private.
If not working after install, restart VSCode.

https://github.com/rjmacarthy/twinny

### tlm

> Local CLI Copilot, powered by CodeLLaMa

https://github.com/yusufcanb/tlm


## Developer agents (more advanced features)

### OpenHands (formerly OpenDevin)

> OpenHands agents can do anything a human developer can: modify code, run commands, browse the web, call APIs, and yes—even copy code snippets from StackOverflow.

https://github.com/All-Hands-AI/OpenHands

### Cline (formerly claude-dev)

> Autonomous coding agent right in your IDE, capable of creating/editing files, executing commands, and more with your permission every step of the way.

https://github.com/cline/cline

### Roo Code (formerly Roo Cline, fork of Cline)

> Roo Code is an AI-powered autonomous coding agent that lives in your editor.

https://github.com/RooVetGit/Roo-Code

[Visual Studio Code Extension](https://marketplace.visualstudio.com/items?itemName=RooVeterinaryInc.roo-cline)

### Aider

> aider is AI pair programming in your terminal

- Homepage: https://aider.chat/
- Blog: https://aider.chat/blog/
- Source: https://github.com/Aider-AI/aider
- Model comparison: https://aider.chat/docs/leaderboards/

[Getting Started](https://aider.chat/#getting-started):

```sh
python3 -m venv ~/venvs/aider
source ~/venvs/aider/bin/activate

python3 -m pip install aider-install
aider-install

export PATH="/home/user/.local/bin:$PATH"

# Change directory into your codebase
cd /to/your/project

# DeepSeek
aider --model deepseek --api-key deepseek=<key>

# Claude 3.7 Sonnet
aider --model sonnet --api-key anthropic=<key>

# o3-mini
aider --model o3-mini --api-key openai=<key>
```

### Claude Code

> Your code’s new collaborator - Unleash Claude’s raw power directly in your terminal. Search million-line codebases instantly. Turn hours-long workflows into a single command. Your tools. Your workflow. Your codebase, evolving at thought speed.

Agentic, requires subscription.

- Homepage: [anthropic.com/claude-code](https://www.anthropic.com/claude-code)
- Quickstart: [docs.anthropic.com → Claude Code Quickstart](https://docs.anthropic.com/en/docs/claude-code/quickstart)
- Awesome Claude Code: [Github → awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)

Install:

```sh
sudo apt install npm
npm install -g @anthropic-ai/claude-code
```
