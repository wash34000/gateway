::

    ____                   __  __       _   _
   / __ \                 |  \/  |     | | (_)
  | |  | |_ __   ___ _ __ | \  / | ___ | |_ _  ___ ___
  | |  | | '_ \ / _ \ '_ \| |\/| |/ _ \| __| |/ __/ __|
  | |__| | |_) |  __/ | | | |  | | (_) | |_| | (__\__ \
   \____/| .__/ \___|_| |_|_|  |_|\___/ \__|_|\___|___/
         | |            
         |_|          

This is the OpenMotics code repository.

Current contents:

* Gateway source
* Cloud source

Branches:

* **default** - The default development branch
* **release_X_X** - A branch for each of the released versions

A mercurial cheat sheet:

* **hg update -r <branch>** - Update to a certain branch                      
* **hg pull -u** - Update current workbench to last code
* **hg status** - View outstanding changes
* **hg addremove** - Add/remove all new/deleted files in one command
* **hg commit** - Commit outstanding changes. Your default editor will be opened to provide a commit message
* **hg push** - Push your pending commits to the remote repository (bitbucket)
* **hg graft -e -r <revision>** - Graft a given change into the current active branch

Example for the grafting:

#. **hg update -r release_1_0** - Update your workbench to the release_1_0 branch
#. **hg pull -u** - Always make sure you have the latest code
#. (apply your changes to the code)
#. **hg commit** - Commit your changes to the release_1_0 branch. You will be asked for a commit message
#. **hg push** - Push your changes to the remote repository. Verify the revision
#. **hg update -r default** - Update your workbench to the default branch (development)
#. **hg pull -u** - Always make sure you have the latest code
#. **hg graft -e -r 60f7daa** - Graft revision 60f7daa from the release_1_0 branch  into the current (default) branch. You will be asked for a commit message
#. **hg push** - Push the grafted change to the remote repository.

