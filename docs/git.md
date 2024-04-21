# Git

## Reposirory cleanup

[Nobody Cares About Your Git History](https://spin.atomicobject.com/git-history/) ...but don't leave any secrets in it.

**git-filter-repo** - Quickly rewrite git repository history (filter-branch replacement)

- [git-filter-repo](https://github.com/newren/git-filter-repo/blob/main/INSTALL.md)
- [Cheat Sheet: Converting from BFG Repo Cleaner](https://github.com/newren/git-filter-repo/blob/main/Documentation/converting-from-bfg-repo-cleaner.md#cheat-sheet-conversion-of-examples-from-bfg) ([BFG](https://rtyley.github.io/bfg-repo-cleaner/))

### Deleting files

```shell
git-filter-repo --use-base-name --path id_dsa --path id_rsa --invert-paths
```

### Removing sensitive content

```shell
git-filter-repo --replace-text passwords.txt
```

Example `passwords.txt`:
```
mypassw0rd==>SomeSecureValueGoesHere
otherPassword==>SomeSecureValueGoesHere
```

### Author

```shell
git filter-repo --mailmap mailmap.txt
```

Example `mailmap.txt`:
```
Correct Name <correct@email.com> <old@email.com>
```

More mailmap examples: https://git-scm.com/docs/gitmailmap#_examples
