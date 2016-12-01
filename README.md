## Git hooks for redmine

This script can be used as a backend for pull request related git hooks. Its
main purpose is to provide some consistency tests between a pull request and
the associated redmine issue.

It will check consistency between 'bug' / 'enhancement' labels and the
associated issues in redmine. The reference to redmine is expected in the last
line of the pull request body :

```
<title>

<long descriptions>

Fix / Ref #XXXX
```

The script will look for a configuration file in the `$HOOK_CONFIG_FILE`
environment variable. This file should have the following structure:

```
{
    "github_token": "secret token here",
    "redmine_url": "https://redmine.my-domain.com",
    "redmine_token": "secret token here too",
    "redmine_bug_ids": [1],  // Which redmine issue types are bugs
    "redmine_feature_ids": [2, 3],  // Which redmine issue type are features
    "redmine_project_matches": {
        "my_git_user/my_git_project": [
            [id1, "Redmine Project 1"],
            [id2, "Coog-Redmine Project 2"]
        ]
    },
    "description_urls": {
        "commit_title": "link to how to write a good title",
        "commit_body": "link to how to write a good body",
        "labels": "link to what rules apply to labels",
        "contents": "link to what rules apply to the content"
    }
}
```
