$ARGUMENTS

You will create a folder ".trees" if it doesn't already exist. And then you will navigate to that folder and add a new git worktree for every worktree specified in the arguments.

Example command: "/multiple-worktrees write tests, add feature"
Example response: Create a folder ".trees" in the root directory, and create subfolders ".trees/write_tests" and ".trees/add_feature". Make the name concise if possible.

Verify the creation of the subtree by doing git branch -a.