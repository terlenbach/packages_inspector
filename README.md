# Packages inspector

Explore a Python codebase, discover the required Python modules, interactively create the mapping Python module -> Python package (or use a specified one), and find out what are your **missing dependencies** and your **unused dependencies**.

![](packages_inspector.gif)

## Quick start

*packages_inspector* is a pure Python 3.8 tool.

One easy way to get a Python 3.8 interpreter available on your machine is using pyenv which can be installed following this guide: [https://github.com/pyenv/pyenv#installation](https://github.com/pyenv/pyenv#installation).

Once you have pyenv installed and ready, here are the commands to get Python 3.8:

```
# Install Python 3.8

pyenv install 3.8.3

# Make it the standard python interpreter

pyenv global 3.8.3
```

Then you can install *packages_inspector* with:

```
python -m pip install .
```

There also exists a dockerfile to build the tool as a docker image.
This can be achieved with:

```
docker build -t packages_inspector .
```

## Why this tool?

Maintaining the list of required dependencies is getting harder and harder over time and especially for large codebases. Some tools already exist, like `pipenv` which provides the `--unused` option. That works well if your project follows basic assumptions:
* no modification on the PYTHONPATH
* no local module has the same name as a module brought by one of your dependencies
* your packages are well mapped in this list https://github.com/bndr/pipreqs/blob/master/pipreqs/mapping

This tool is here to help you if one of these bullet points is wrong in your case, like for Django projects.

## Usage

The only mandatory agument is the path of the codebase you want to inspect.

If you provide a *requirements.txt* file or a *Pipfile* file, then the list of already present dependencies will be used to ease the mapping of your modules. As an example, if your codebase requires the module *waffle*, without any requirements specified, the program will use pip search to find a suitable package, and the proposed mapping will be *waffle* -> *waffle*, but if in your requirements, let's say you have the dependency *django-waffle*, then the mapping *waffle* -> *django-waffle* will be the first proposition that you'll get.

There is also the possibility to add extra modules (option `-e`), if for example some modules are dynamically loaded at runtime based on configuration.

You can also explicitly ignore modules (option `-i`), if for instance you know they come from a standard library.

You can also set explicit mapping in the form `-m <module>:<package>`.

Once you've answered all the questions, a context file will be generated (`./.packages-inspector.yaml` by default), and reused during the next calls to the program. It contains the mappings, the ignored modules, and the extra modules to consider.

This file is dependent to the codebase and can therefore be tracked via a version control system.

To make sure you don't forget to add a required dependency or that you clean your no longer needed dependencies, you can from time to time rerun the program with your context file and with the option `--error-on-diff` which will make the program exit with the exit code 1, this is especially useful if you want to automate that process in your CI workflow.

## Pre-commit

You can make this tool automatically run via [pre-commit](https://pre-commit.com/pre-commit) by adding this section to your pre-commit configuration file:

```
  - repo: git@github.com:terlenbach/packages_inspector.git
    rev: 0.1
    hooks:
      - id: packages-inspector
        args:
          [
            "--requirements=requirements.txt",
            "--context-file=.packages_inspector.yaml",
            "--error-on-diff",
            "--no-interaction",
            "--no-pypi-calls",
            "--no-update-context-file",
          ]
```

## Contributing

For development purpose, you can use `pipenv` to create a virtualenv and to install the dev dependencies, as follows:

```
# Install pipenv
python -m pip install pipenv

# Create the Venv and install the dev dependencies
pipenv sync --dev

# Run the unit tests
pipenv run tests

# Login to the Venv
pipenv shell

# Run the cli
packages_inspector --help
```

Running `pipenv sync --dev` installs the packages_inspector package in editable mode in the virtualenv.

#### Pipfile, setup.py, requirements.txt

`Pipfile` is the file required by `Pipenv`.
It contains the list of dependencies for rolling out the package and for working on it (the dev-packages).
`Pipenv` resolves the depdency graph and locks the solution in a file named `Pipfile.lock`.
Once locked, the package dependencies are dumped into a `requirements.txt` file with this command `pipenv lock -r > requirements.txt`.
This `requirements.txt` file will then be used by the `setup.py`file.
`Pipenv` is therefore only required while working on the package.

#### Pre-commit

This folder contains a pre-commit configuration file so that [pre-commit](https://pre-commit.com/) can
be used to run some checks and automatically fix some problems before committing. To do that, run:

```
pre-commit run
```

Before starting to modify the project it can be a good idea to install it as a git hook that will
make sure pre-commit is run before committing any change. This can be done like this:

```
pre-commit install
```

Once done working on the agent, the hook can be uninstalled:

```
pre-commit uninstall
```

Pre-commit automatically runs mainly the following tools:
* [flake8](https://flake8.pycqa.org/en/latest/)
* [black](https://black.readthedocs.io/en/stable/)
* [mypy](https://mypy.readthedocs.io/en/stable/)
* [isort](https://readthedocs.org/projects/isort/)

#### Tests

To run the tests:

```
pipenv run tests
```

