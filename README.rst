===================
FileRescueMatcher
===================

FileRescueMatcher helps you to get back lost file names by comparing your files to a reference directory.


Idea
****

Damaged file systems that were recovered with programs like `extundelete <http://extundelete.sourceforge.net/>`_, typos in batch commands or file-eating dogs sometimes leave you with messed up file names like `rescue0001` or `b0bba64fd3b00010127d839a32ba3183` or sensible, but swapped file names.

If you have older versions of your files available, FileRescueMatcher can scan through them, compare them to your nameless files and tell you which files look most alike.


Usage
*****

::

  python filerescuematcher.py leftdirectory rightdirectory

This will recursively go through all files in ``leftdirectory`` and for each of them print out how similar each file from ``rightdirectory`` is.

``leftdirectory`` is usually the directory that contains the old versions of the files. ``rightdirectory`` usually is the directory with the lost file names::

  python filerescuematcher.py MY-OLD-BACKUP RECOVERED-FILES 

* In most cases, you might want to only print out matches that exceed a certain similarity ratio. The option ``--min_ratio 0.5`` will only print out files from ``rightdirectory`` that share at least half of the lines with the file they are compared to.
* If you pass the option ``--mimetype-filter``, FileRescueMatcher will compare the mimetypes first and skip the comparison if they don't match.
* In addition to displaying which files are similar, `best matching` files can also be copied to a different directory by passing the ``--copy-dest DIRECTORY`` option. By default, the `best matching` file is the one with the highest similarity ratio. If for a file from ``leftdirectory`` a `best matching` file from ``rightdirectory`` has been found, that file is copied to the directory specified after ``--copy-dest``, and gets the file name of the corresponding file from ``leftdirectory``. For example, if ``leftdirectory/myfile.txt`` matches best with ``rightdirectory/file003`` and the option ``--copy-dest outputdir`` is specified, ``rightdirectory/file003`` will be saved as ``outputdir/leftdirectory/myfile.txt``.
* Sometimes, you don't want the `best matching` file to be the file with the highest similarity ratio, e.g. when ``rightdirectory`` contains different versions of a file and the right one is the one with the most changes (this might especially be the case if you used a version control system like GIT). In this case, add the ``--copy-least-matching`` option to make the `best matching` file the one with the lowest similarity ratio that still exceeds ``--min-ratio``. This option only really makes sense with a good choice for the ``--min-ratio`` option!
* You can see all possible options by running ``filerescuematcher.py --help``.

You should try to narrow down the directories as far as possible because **FileRescueMatcher has to compare every file from the left one with every file from the right one**! If you know that the files are interested in are in one particular subdirectory, use that instead of a parent directory!


Example
*******

I once developed a patch for `GTK <http://www.gtk.org/>`_ in a `GIT <http://git-scm.com/>`_ repository when my Ext4 file system got corrupted and all work seemed lost.

I used `extundelete <http://extundelete.sourceforge.net/>`_ to recover the files into a directory ``RECOVER``, but all file names were lost.

I knew that all files I had changed contained the string `GDK_SMOOTH_SCROLL`, so I used ``grep -r -l GDK_SMOOTH_SCROLL RECOVER`` to get all recovered files which contained that string and copied them into a directory `INTERESTING`.

After that, I downloaded the original GTK version on which I had based my work to a ``gtk`` directory. I also knew that I had only changed files from the ``gtk/gtk+-3.0.12/gdk`` subdirectory, so I ran::

  python filerescuematcher.py gtk/gtk+-3.0.12/gdk INTERESTING --mimetype-filter --min-ratio 0.7 --copy-dest MATCHED --copy-least-matching

and ended up with my lost files being saved in the ``MATCHED`` directory. Day made!


Restrictions
************

* Python 2.7 or higher or Python 3.2 or higher required.
* FileRescueMatcher currently only runs on Linux (and possibly other UNIX-like systems). If you need it for your platform, contact the author or supply a patch.
* Only text files can be matched, binary files are not supported yet. It should  be fairly easy to extend it to also allow matching binary files, though.


LICENSE
*******

FileRescueMatcher is Free Software (MIT-licensed).

If you need a different license for any reason, contact the author.
