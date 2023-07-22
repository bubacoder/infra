#!/bin/sh

echo ">>> Ansible-lint"
(cd ansible && ansible-lint)

echo ">>> ShellCheck"
find . -type f -name "*.sh" -exec shellcheck --format=tty {} \;
