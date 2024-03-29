# Git

## Repo cleanup

**git-filter-repo** - Quickly rewrite git repository history (filter-branch replacement)

[git-filter-repo](https://github.com/newren/git-filter-repo/blob/main/INSTALL.md)
[Cheat Sheet: Converting from BFG Repo Cleaner](https://github.com/newren/git-filter-repo/blob/main/Documentation/converting-from-bfg-repo-cleaner.md#cheat-sheet-conversion-of-examples-from-bfg)

```shell
# Deleting files
git filter-repo --use-base-name --path id_dsa --path id_rsa --invert-paths

# Removing sensitive content
git filter-repo --replace-text passwords.txt
```

