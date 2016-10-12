# iHateDarcs
a python gui for darcs

## DISCLAIMER:
as of now
* A lot of things are hardcoded
* everything is optimized for my personal workflow only
* the tools supported are exactly the ones I use in my working environment

## Features

So far the following features are supported:

* darcs record
* darcs amend
* darcs show dependencies
* darcs diff
* darcs pull
* darcs send

moreover integration with the redmine issue tracker:

* edit issues
* edit new issues
* reference issues in darcs-patches

Also a preliminary basic support for rietveld:

* view open reviews for me in a browser


## Requirements

* python 3.4
* darcs 2.12.0 (highly recommended to use that exact version)
* meld (diff viewer)
* graphviz
* gnu diffutils (the diff command)
* gnu patch
* PyQt4 or PyQt5 (required for guidata. Ubuntu reps: python3-pyqtX - alternatively via pypi)
* kivy 
```add-apt-repository ppa:kivy-team/kivy
apt-get update
apt-get install python3-kivy
(https://kivy.org/docs/installation/installation-linux.html)
```

**regarding the darcs version**
There have been slight output changes, in darcs 2.12 and the gui wraps the darcs cli client.
trying to use the gui with an earlier version might result in errors, unwanted local repository states
I guarantee for nothing!

It is recommended to install darcs with `stack install darcs-2.12.0`.

moreover you need the following PyPI packages:
(install with `sudo pip3 install <package-name>`)

* guidata
* pexpect
* python-redmine
* rietveld
* lazy
* lxml
* pyaml
* graphviz
* pydot
* spyder